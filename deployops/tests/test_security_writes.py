import frappe
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user
from frappe.tests.test_api import make_request
from frappe.utils import get_test_client, get_url

from deployops.api import checklists as checklist_api
from deployops.roles import ADMINISTRATOR, MANAGER, SUPERVISOR, TECHNICIAN
from deployops.security.matrix import DOCTYPE_MATRIX
from deployops.tests import erpnext_fixtures as fx
from deployops.tests.test_checklists import ChecklistTestCase
from deployops.tests.utils import api_token
from deployops.workflow import job_workflow

JOB = "DeployOps Job"
FORM = "DeployOps Cashmatic Pre-installation"
ALLOCATION = "DeployOps Equipment Allocation"
CATEGORY = "_Sec Cash"
PREFIX = f"sec-{frappe.generate_hash(length=6)}"


class TestWritesOverHttp(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		fx.make_company()
		cls.item = fx.make_item("_Sec CR-460")
		cls.customer = fx.make_customer(f"_SecCust {PREFIX}")
		for serial in ("SEC-SN-1", "SEC-SN-2"):
			fx.make_serial(serial, cls.item)
		frappe.get_doc(
			{
				"doctype": "DeployOps Equipment Category",
				"category_name": CATEGORY,
				"product_line": "Cashmatic",
				"items": [{"item_code": cls.item}],
			}
		).insert(ignore_permissions=True)

		cls.users = {}
		for key, role in (
			("tech", TECHNICIAN),
			("other", TECHNICIAN),
			("sup", SUPERVISOR),
			("man", MANAGER),
			("admin", ADMINISTRATOR),
		):
			email = f"{PREFIX}-{key}@deployops.test"
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": key,
					"send_welcome_email": 0,
					"roles": [{"role": role}],
				}
			).insert(ignore_permissions=True)
			if role != ADMINISTRATOR:
				frappe.get_doc(
					{
						"doctype": "DeployOps Equipment Access Profile",
						"user": email,
						"categories": [{"category": CATEGORY}],
					}
				).insert(ignore_permissions=True)
			cls.users[key] = email

		# A preparation job for two machines: one checklist left as a draft, one submitted.
		cls.order = fx.make_sales_order(cls.customer, [cls.item, cls.item]).name
		cls.job = (
			frappe.get_doc(
				{
					"doctype": JOB,
					"job_type": "Pre-installation",
					"company": fx.COMPANY,
					"source_doctype": "Sales Order",
					"source_name": cls.order,
					"assigned_technician": cls.users["tech"],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
		with set_user(cls.users["sup"]):
			job_workflow.apply_job_action(cls.job, "start")
		job = frappe.get_doc(JOB, cls.job)
		job.devices[0].serial_no, job.devices[1].serial_no = "SEC-SN-1", "SEC-SN-2"
		job.save(ignore_permissions=True)
		helper = ChecklistTestCase("complete")  # reuses its "answer every required field" helpers
		with set_user(cls.users["tech"]):
			cls.draft, cls.submitted = (
				checklist_api.start_checklist(cls.job, row.name)["name"] for row in job.devices
			)
			doc = helper.complete(frappe.get_doc(FORM, cls.submitted))
			doc.save()
			doc.submit()
		cls.files = frappe.get_all(
			"File", filters={"attached_to_doctype": FORM, "attached_to_name": cls.submitted}, pluck="name"
		)
		cls.allocations = frappe.get_all(
			ALLOCATION, filters={"serial_no": ["like", "SEC-SN-%"]}, pluck="name"
		)

		# A delivery of the same item, for direct-URL checks on ERPNext records.
		bundle = fx.make_bundle(cls.item, ["SEC-SN-2"])
		cls.delivery = fx.make_delivery_note(
			cls.customer, [{"item_code": cls.item, "serial_and_batch_bundle": bundle}]
		).name

		cls.tokens = {key: api_token(user) for key, user in cls.users.items()}
		frappe.db.commit()  # nosemgrep
		cls.client = get_test_client(use_cookies=False)

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for name in (cls.draft, cls.submitted):  # submitted forms can't go through delete_doc
			for table in (
				"DeployOps Checklist Photo",
				"DeployOps Checklist Opening Hours",
				"DeployOps Checklist Signature",
			):
				frappe.db.delete(table, {"parent": name})
			frappe.db.delete(FORM, {"name": name})
		frappe.db.delete(ALLOCATION, {"name": ["in", cls.allocations or [""]]})
		fx.purge(
			names={
				"File": cls.files,
				JOB: [cls.job],
				"DeployOps Equipment Access Profile": list(cls.users.values()),
				"DeployOps Equipment Category": [CATEGORY],
				"User": list(cls.users.values()),
				"Customer": [cls.customer],
				"Item": [cls.item],
			}
		)
		frappe.db.commit()  # nosemgrep
		super().tearDownClass()

	# --- helpers ---------------------------------------------------------------------------------

	def call(self, method, path, who=None, json=None, params=None):
		target = getattr(self.client, method)
		kwargs = {"query_string": params or {}}
		if who:
			kwargs["headers"] = {"Authorization": self.tokens[who]}
		if json is not None:
			kwargs["json"] = json
		return make_request(target=target, args=(get_url(path),), kwargs=kwargs)

	def state(self, doctype, name):
		frappe.db.rollback()  # a fresh read: see what the request threads committed
		return frappe.db.get_value(doctype, name, ["modified", "docstatus"], as_dict=True)

	def assert_refused(self, response, doctype, name, before):
		self.assertEqual(response.status_code, 403, response.data[:300])
		self.assertEqual(self.state(doctype, name), before)

	# --- DeployOps records -----------------------------------------------------------------------

	def test_requests_run_as_the_given_user(self):
		"""Guards every test below: a refusal must come from the user's rights, not a lost login."""
		for who, user in self.users.items():
			with self.subTest(who=who):
				response = self.call("get", "/api/method/frappe.auth.get_logged_user", who)
				self.assertEqual(response.json["message"], user)

	def test_checklist_changes_only_by_the_assigned_technician(self):
		path = f"/api/resource/{FORM}/{self.draft}"
		before = self.state(FORM, self.draft)
		for who in ("other", "sup", "man", "admin"):
			with self.subTest(who=who):
				response = self.call("put", path, who, json={"additional_remarks": f"by {who}"})
				self.assert_refused(response, FORM, self.draft, before)

		response = self.call("put", path, "tech", json={"additional_remarks": "by the technician"})
		self.assertEqual(
			response.status_code, 200, response.data[:1500]
		)  # the same request works for the assignee
		frappe.db.rollback()
		self.assertEqual(frappe.db.get_value(FORM, self.draft, "additional_remarks"), "by the technician")

	def test_checklists_are_not_created_or_submitted_by_others(self):
		before_count = frappe.db.count(FORM)
		for who in ("sup", "man", "admin"):
			with self.subTest(action="create", who=who):
				response = self.call(
					"post", f"/api/resource/{FORM}", who, json={"job": self.job, "job_device": "x"}
				)
				self.assertEqual(response.status_code, 403, response.data[:300])
				frappe.db.rollback()
				self.assertEqual(frappe.db.count(FORM), before_count)

		before = self.state(FORM, self.draft)
		for who in ("other", "sup", "man", "admin"):
			with self.subTest(action="submit", who=who):
				doc = frappe.get_doc(FORM, self.draft).as_dict(convert_dates_to_str=True)
				response = self.call("post", "/api/method/frappe.client.submit", who, json={"doc": doc})
				self.assert_refused(response, FORM, self.draft, before)

	def test_only_a_manager_cancels_a_submitted_checklist(self):
		before = self.state(FORM, self.submitted)
		for who in ("tech", "other", "sup", "admin"):
			with self.subTest(who=who):
				response = self.call(
					"post",
					"/api/method/frappe.client.cancel",
					who,
					json={"doctype": FORM, "name": self.submitted},
				)
				self.assert_refused(response, FORM, self.submitted, before)
		self.assertEqual(before.docstatus, 1)

	def test_nobody_deletes_operational_records(self):
		for doctype, name in ((JOB, self.job), (FORM, self.draft), (ALLOCATION, self.allocations[0])):
			before = self.state(doctype, name)
			for who in ("tech", "sup", "man", "admin"):
				with self.subTest(doctype=doctype, who=who):
					response = self.call("delete", f"/api/resource/{doctype}/{name}", who)
					self.assert_refused(response, doctype, name, before)

	def test_jobs_are_not_created_by_technicians_nor_changed_by_another_technician(self):
		before_count = frappe.db.count(JOB)
		response = self.call(
			"post",
			f"/api/resource/{JOB}",
			"tech",
			json={
				"job_type": "Pre-installation",
				"company": fx.COMPANY,
				"source_doctype": "Sales Order",
				"source_name": self.order,
			},
		)
		self.assertEqual(response.status_code, 403, response.data[:300])
		frappe.db.rollback()
		self.assertEqual(frappe.db.count(JOB), before_count)

		before = self.state(JOB, self.job)
		response = self.call(
			"put", f"/api/resource/{JOB}/{self.job}", "other", json={"planned_date": "2030-01-01"}
		)
		self.assert_refused(response, JOB, self.job, before)

	def test_print_and_export_follow_the_matrix(self):
		response = self.call("get", "/printview", "other", params={"doctype": FORM, "name": self.submitted})
		self.assertNotEqual(response.status_code, 200)  # a technician not on the job
		response = self.call("get", "/printview", "tech", params={"doctype": FORM, "name": self.submitted})
		self.assertEqual(response.status_code, 200)

		export = {"doctype": FORM, "file_format_type": "CSV", "fields": '["name"]'}
		for who, allowed in (("tech", False), ("sup", False), ("man", True), ("admin", True)):
			with self.subTest(who=who):
				response = self.call(
					"get", "/api/method/frappe.desk.reportview.export_query", who, params=export
				)
				if allowed:
					self.assertEqual(response.status_code, 200)
				else:
					self.assertEqual(response.status_code, 403, response.data[:300])

	def test_every_refusal_in_the_matrix_holds_over_http(self):
		"""Each right the matrix withholds (create, write, print, export) is refused on a real record.

		Print is the one Frappe doesn't enforce by itself (read is enough there); see print_permissions.py.
		"""
		roles = {"tech": TECHNICIAN, "sup": SUPERVISOR, "man": MANAGER, "admin": ADMINISTRATOR}
		records = {
			JOB: (self.job, {"planned_date": "2030-01-01"}),
			ALLOCATION: (self.allocations[0], {"return_condition": "Damaged"}),
			"DeployOps Equipment Category": (CATEGORY, {"description": "changed"}),
			"DeployOps Equipment Access Profile": (self.users["tech"], {"enabled": 0}),
			"DeployOps Reference Files": ("DeployOps Reference Files", {"docstatus": 0}),
		}
		for doctype, (name, change) in records.items():
			for who, role in roles.items():
				letters = DOCTYPE_MATRIX[doctype][role]
				if "w" not in letters:
					with self.subTest(doctype=doctype, who=who, right="write"):
						before = self.state(doctype, name)
						response = self.call("put", f"/api/resource/{doctype}/{name}", who, json=change)
						self.assert_refused(response, doctype, name, before)
				if "c" not in letters and doctype != "DeployOps Reference Files":  # a single
					with self.subTest(doctype=doctype, who=who, right="create"):
						count = frappe.db.count(doctype)
						response = self.call("post", f"/api/resource/{doctype}", who, json={})
						self.assertEqual(response.status_code, 403, response.data[:300])
						frappe.db.rollback()
						self.assertEqual(frappe.db.count(doctype), count)
				if "p" not in letters:
					with self.subTest(doctype=doctype, who=who, right="print"):
						response = self.call(
							"get", "/printview", who, params={"doctype": doctype, "name": name}
						)
						self.assertEqual(response.status_code, 403, response.data[:300])
				if "e" not in letters and doctype != "DeployOps Reference Files":
					with self.subTest(doctype=doctype, who=who, right="export"):
						params = {"doctype": doctype, "file_format_type": "CSV", "fields": '["name"]'}
						response = self.call(
							"get", "/api/method/frappe.desk.reportview.export_query", who, params=params
						)
						self.assertEqual(response.status_code, 403, response.data[:300])

		# Positive control: the same print works for a role the matrix gives it to.
		response = self.call("get", "/printview", "sup", params={"doctype": JOB, "name": self.job})
		self.assertEqual(response.status_code, 200)

	# --- ERPNext records by URL --------------------------------------------------------------------

	def test_roles_cannot_open_or_print_erpnext_records_by_url(self):
		records = (
			("Serial No", "SEC-SN-1"),
			("Sales Order", self.order),
			("Delivery Note", self.delivery),
		)
		for who in ("tech", "sup", "man", "admin"):
			for doctype, name in records:
				with self.subTest(who=who, doctype=doctype):
					self.assertEqual(
						self.call("get", f"/api/resource/{doctype}/{name}", who).status_code, 403
					)
					response = self.call(
						"get", "/api/method/frappe.client.get", who, params={"doctype": doctype, "name": name}
					)
					self.assertEqual(response.status_code, 403)
					response = self.call("get", "/printview", who, params={"doctype": doctype, "name": name})
					self.assertNotEqual(response.status_code, 200)
					before = self.state(doctype, name)
					response = self.call("put", f"/api/resource/{doctype}/{name}", who, json={"remarks": "x"})
					self.assert_refused(response, doctype, name, before)
