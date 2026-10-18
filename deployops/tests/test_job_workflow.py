import json

import frappe
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user
from frappe.tests.test_api import make_request
from frappe.utils import get_test_client, get_url

from deployops.api import jobs as job_api
from deployops.roles import ADMINISTRATOR, MANAGER, SUPERVISOR, TECHNICIAN
from deployops.tests import erpnext_fixtures as fx
from deployops.tests.test_job import JOB, JobTestCase, make_job
from deployops.tests.test_security_negative import login_sid
from deployops.tests.utils import make_role_user


class WorkflowTestCase(JobTestCase):
	def setUp(self):
		super().setUp()
		self.manager = make_role_user(MANAGER)
		self.admin = make_role_user(ADMINISTRATOR)
		frappe.get_doc(
			{
				"doctype": "DeployOps Equipment Access Profile",
				"user": self.manager,
				"categories": [{"category": "_Test Cash"}],
			}
		).insert(ignore_permissions=True)

	def installation_job(self, serials=("JOB-CR-1", "JOB-CR-2")):
		bundle = fx.make_bundle(self.cash, list(serials))
		note = fx.make_delivery_note(
			self.customer, [{"item_code": self.cash, "serial_and_batch_bundle": bundle}]
		).name
		return make_job("Delivery Note", note, assigned_technician=self.technician).name

	def act(self, user, job, action, reason=None):
		with set_user(user):
			return job_api.job_action(job, action, reason)

	def machine(self, user, job, idx, action, reason=None):
		device = frappe.get_doc(JOB, job).devices[idx].name
		with set_user(user):
			return job_api.device_action(job, device, action, reason)

	def finish_machines(self, job):
		for idx in range(len(frappe.get_doc(JOB, job).devices)):
			self.machine(self.technician, job, idx, "start")
			self.machine(self.technician, job, idx, "complete")

	def status(self, job):
		return frappe.db.get_value(JOB, job, "status")


class TestPaths(WorkflowTestCase):
	def test_installation_path_with_log(self):
		job = self.installation_job()
		self.assertEqual(self.act(self.supervisor, job, "start"), "Ready for Deployment")
		self.assertEqual(self.act(self.technician, job, "arrive"), "On Site")
		self.finish_machines(job)
		self.assertEqual(self.act(self.technician, job, "submit"), "Pending Review")
		self.assertEqual(self.act(self.supervisor, job, "approve"), "Completed")

		doc = frappe.get_doc(JOB, job)
		self.assertEqual({d.device_status for d in doc.devices}, {"Completed"})
		moves = [
			(log.action, log.from_status, log.to_status, log.user) for log in doc.status_log if not log.device
		]
		self.assertEqual(
			moves,
			[
				("start", "Draft", "Ready for Deployment", self.supervisor),
				("arrive", "Ready for Deployment", "On Site", self.technician),
				("submit", "On Site", "Pending Review", self.technician),
				("approve", "Pending Review", "Completed", self.supervisor),
			],
		)
		self.assertEqual(len([log for log in doc.status_log if log.device]), 4)  # 2 machines x start/complete
		self.assertTrue(all(log.timestamp for log in doc.status_log))

	def test_pre_installation_path_serial_picked_during_preparation(self):
		order = fx.make_sales_order(self.customer, [self.cash]).name
		job = make_job(
			"Sales Order", order, job_type="Pre-installation", assigned_technician=self.technician
		).name
		self.assertEqual(self.act(self.supervisor, job, "start"), "In Preparation")
		self.machine(self.technician, job, 0, "start")
		with self.assertRaises(frappe.ValidationError):
			self.machine(self.technician, job, 0, "complete")  # no serial yet

		with set_user(self.technician):
			doc = frappe.get_doc(JOB, job)
			doc.devices[0].serial_no = "JOB-CR-3"
			doc.save()
		self.machine(self.technician, job, 0, "complete")
		self.act(self.technician, job, "submit")
		self.assertEqual(self.act(self.manager, job, "approve"), "Completed")

	def test_maintenance_goes_straight_on_site(self):
		visit = fx.make_maintenance_visit(
			self.customer, [{"item_code": self.cash, "serial_no": "JOB-CR-1"}]
		).name
		job = make_job(
			"Maintenance Visit", visit, job_type="Maintenance", assigned_technician=self.technician
		).name
		self.assertEqual(self.act(self.supervisor, job, "start"), "On Site")

	def test_closing_the_source_later_does_not_stop_the_job(self):
		order = fx.make_sales_order(self.customer, [self.cash])
		job = make_job(
			"Sales Order", order.name, job_type="Pre-installation", assigned_technician=self.technician
		).name
		order.db_set("status", "Closed")
		self.assertEqual(self.act(self.supervisor, job, "start"), "In Preparation")


class TestRules(WorkflowTestCase):
	def assert_refused(self, user, job, action, reason=None, exc=frappe.ValidationError):
		with self.assertRaises(exc):
			self.act(user, job, action, reason)

	def test_start_needs_an_assigned_technician(self):
		order = fx.make_sales_order(self.customer, [self.cash]).name
		job = make_job("Sales Order", order, job_type="Pre-installation").name
		self.assert_refused(self.supervisor, job, "start")

	def test_who_may_do_what(self):
		job = self.installation_job()
		self.assert_refused(self.technician, job, "start", exc=frappe.PermissionError)
		self.assert_refused(self.admin, job, "start", exc=frappe.PermissionError)  # Admin does not approve
		self.act(self.supervisor, job, "start")
		self.assert_refused(
			self.supervisor, job, "arrive", exc=frappe.PermissionError
		)  # assigned technician only
		self.act(self.technician, job, "arrive")
		self.finish_machines(job)
		self.assert_refused(self.supervisor, job, "submit", exc=frappe.PermissionError)
		self.act(self.technician, job, "submit")
		self.assert_refused(self.technician, job, "approve", exc=frappe.PermissionError)
		self.assert_refused(
			self.supervisor, job, "cancel", "x", exc=frappe.PermissionError
		)  # Manager / Admin only

	def test_actions_must_fit_the_current_state(self):
		job = self.installation_job()
		self.assert_refused(self.supervisor, job, "approve")
		self.assert_refused(self.technician, job, "submit")

	def test_reason_required_to_block_return_and_cancel(self):
		job = self.installation_job()
		self.act(self.supervisor, job, "start")
		self.assert_refused(self.technician, job, "block", "  ")
		self.assert_refused(self.manager, job, "cancel")
		self.act(self.technician, job, "arrive")
		self.finish_machines(job)
		self.act(self.technician, job, "submit")
		self.assert_refused(self.supervisor, job, "return")

	def test_submit_needs_every_machine_done_and_none_blocked(self):
		job = self.installation_job()
		self.act(self.supervisor, job, "start")
		self.act(self.technician, job, "arrive")
		self.machine(self.technician, job, 0, "start")
		self.machine(self.technician, job, 0, "complete")
		self.assert_refused(self.technician, job, "submit")  # second machine pending

		self.machine(self.technician, job, 1, "block", "Wall socket missing")
		self.assert_refused(self.technician, job, "submit")  # blocked machine

		self.machine(self.supervisor, job, 1, "cancel", "Customer keeps one machine in storage")
		self.assertEqual(self.act(self.technician, job, "submit"), "Pending Review")  # cancelled is fine

	def test_all_machines_cancelled_cannot_be_submitted(self):
		job = self.installation_job(serials=("JOB-CR-1",))
		self.act(self.supervisor, job, "start")
		self.act(self.technician, job, "arrive")
		self.machine(self.supervisor, job, 0, "cancel", "Not installed")
		self.assert_refused(self.technician, job, "submit")


class TestBlockReturnCancel(WorkflowTestCase):
	def test_block_and_unblock_returns_to_previous_state(self):
		job = self.installation_job()
		self.act(self.supervisor, job, "start")
		self.act(self.technician, job, "arrive")
		self.assertEqual(self.act(self.technician, job, "block", "Site closed"), "Blocked")
		with self.assertRaises(frappe.PermissionError):
			self.act(self.technician, job, "unblock")
		self.assertEqual(self.act(self.supervisor, job, "unblock"), "On Site")
		log = frappe.get_doc(JOB, job).status_log
		self.assertEqual((log[-2].action, log[-2].reason), ("block", "Site closed"))

	def test_return_for_correction_then_resubmit(self):
		job = self.installation_job()
		self.act(self.supervisor, job, "start")
		self.act(self.technician, job, "arrive")
		self.finish_machines(job)
		self.act(self.technician, job, "submit")
		self.assertEqual(
			self.act(self.supervisor, job, "return", "Photo of the cash box missing"),
			"Returned for Correction",
		)
		self.assertEqual(self.act(self.technician, job, "submit"), "Pending Review")
		self.assertEqual(self.act(self.supervisor, job, "approve"), "Completed")

	def test_cancel_by_manager_or_admin_and_closed_jobs_are_locked(self):
		job = self.installation_job()
		self.assertEqual(self.act(self.admin, job, "cancel", "Order cancelled by customer"), "Cancelled")
		with self.assertRaises(frappe.ValidationError):
			self.act(self.manager, job, "cancel", "again")
		doc = frappe.get_doc(JOB, job)
		doc.planned_date = "2027-01-01"
		with self.assertRaises(frappe.ValidationError):
			doc.save()

	def test_machines_only_updated_while_work_is_under_way(self):
		job = self.installation_job()
		self.act(self.supervisor, job, "start")  # Ready for Deployment: not on site yet
		with self.assertRaises(frappe.ValidationError):
			self.machine(self.technician, job, 0, "start")


class TestNoBypass(WorkflowTestCase):
	def test_status_fields_and_log_cannot_be_edited_directly(self):
		job = self.installation_job()
		self.act(self.supervisor, job, "start")
		self.act(self.technician, job, "arrive")

		edits = {
			"job status": lambda d: setattr(d, "status", "Completed"),
			"previous status": lambda d: setattr(d, "previous_status", "On Site"),
			"machine status": lambda d: setattr(d.devices[0], "device_status", "Completed"),
			"log row": lambda d: d.append("status_log", {"action": "approve", "to_status": "Completed"}),
			"log removed": lambda d: d.set("status_log", []),
		}
		for label, edit in edits.items():
			with self.subTest(label), set_user(self.technician):
				doc = frappe.get_doc(JOB, job)
				edit(doc)
				with self.assertRaises(frappe.ValidationError):
					doc.save()

	def test_unassigned_technician_cannot_act(self):
		job = self.installation_job()
		self.act(self.supervisor, job, "start")
		other = "_other-tech@deployops.test"
		frappe.get_doc(
			{
				"doctype": "User",
				"email": other,
				"first_name": "Other",
				"send_welcome_email": 0,
				"roles": [{"role": "DeployOps Technician"}],
			}
		).insert(ignore_permissions=True)
		with self.assertRaises(frappe.PermissionError):
			self.act(other, job, "arrive")

	def test_available_actions_per_user(self):
		job = self.installation_job()
		with set_user(self.supervisor):
			self.assertEqual({a["action"] for a in job_api.get_actions(job)["job"]}, {"start"})
		with set_user(self.technician):
			self.assertEqual(job_api.get_actions(job), {"job": [], "devices": {}})
		with set_user(self.admin):
			self.assertEqual({a["action"] for a in job_api.get_actions(job)["job"]}, {"cancel"})

		self.act(self.supervisor, job, "start")
		self.act(self.technician, job, "arrive")
		with set_user(self.technician):
			actions = job_api.get_actions(job)
		self.assertEqual({a["action"] for a in actions["job"]}, {"submit", "block"})
		self.assertEqual(
			{a["action"] for row in actions["devices"].values() for a in row}, {"start", "block"}
		)


class TestMachineIntegrity(WorkflowTestCase):
	def pre_install_job(self):
		order = fx.make_sales_order(self.customer, [self.cash]).name
		job = make_job(
			"Sales Order", order, job_type="Pre-installation", assigned_technician=self.technician
		).name
		self.act(self.supervisor, job, "start")
		return job

	def save_as(self, user, job, edit):
		with set_user(user):
			doc = frappe.get_doc(JOB, job)
			edit(doc)
			doc.save()

	def test_completed_job_cannot_be_cancelled(self):
		job = self.installation_job(serials=("JOB-CR-1",))
		self.act(self.supervisor, job, "start")
		self.act(self.technician, job, "arrive")
		self.finish_machines(job)
		self.act(self.technician, job, "submit")
		self.act(self.supervisor, job, "approve")
		with self.assertRaises(frappe.ValidationError):
			self.act(self.manager, job, "cancel", "too late")
		self.assertEqual(self.status(job), "Completed")

	def test_completed_machine_serial_is_frozen(self):
		job = self.pre_install_job()
		self.save_as(self.technician, job, lambda d: setattr(d.devices[0], "serial_no", "JOB-CR-3"))
		self.machine(self.technician, job, 0, "start")
		self.machine(self.technician, job, 0, "complete")
		with self.assertRaises(frappe.ValidationError):
			self.save_as(self.technician, job, lambda d: setattr(d.devices[0], "serial_no", "JOB-CR-2"))

	def test_machines_cannot_be_removed_after_draft(self):
		job = self.pre_install_job()
		with self.assertRaises(frappe.ValidationError):
			self.save_as(self.technician, job, lambda d: d.set("devices", []))
		with self.assertRaises(frappe.ValidationError):
			self.save_as(self.supervisor, job, lambda d: d.set("devices", []))

	def test_machines_can_be_removed_in_draft(self):
		order = fx.make_sales_order(self.customer, [self.cash, self.robot]).name
		job = make_job("Sales Order", order, job_type="Pre-installation").name
		self.save_as("Administrator", job, lambda d: d.set("devices", d.devices[:1]))
		self.assertEqual(len(frappe.get_doc(JOB, job).devices), 1)

	def test_machine_list_frozen_during_review(self):
		job = self.pre_install_job()
		self.save_as(self.technician, job, lambda d: setattr(d.devices[0], "serial_no", "JOB-CR-3"))
		self.machine(self.technician, job, 0, "start")
		self.machine(self.technician, job, 0, "complete")
		self.act(self.technician, job, "submit")
		with self.assertRaises(frappe.ValidationError):
			self.save_as(self.supervisor, job, lambda d: d.append("devices", {"item_code": self.cash}))


class TestWorkflowOverHttp(IntegrationTestCase):
	"""The workflow API over real HTTP: methods, roles, guests and error codes."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		fx.make_company()
		cls.item = fx.make_item("_Wf CR-460")
		cls.customer = fx.make_customer("_WfCust")
		frappe.get_doc(
			{
				"doctype": "DeployOps Equipment Category",
				"category_name": "_Wf Cash",
				"items": [{"item_code": cls.item}],
			}
		).insert(ignore_permissions=True)
		cls.users = {}
		for key, role in (("tech", TECHNICIAN), ("other", TECHNICIAN), ("sup", SUPERVISOR)):
			email = f"wf-{key}@deployops.test"
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": key,
					"send_welcome_email": 0,
					"roles": [{"role": role}],
				}
			).insert(ignore_permissions=True)
			frappe.get_doc(
				{
					"doctype": "DeployOps Equipment Access Profile",
					"user": email,
					"categories": [{"category": "_Wf Cash"}],
				}
			).insert(ignore_permissions=True)
			cls.users[key] = email
		fx.make_serial("WF-SN-1", cls.item)
		note = fx.make_delivery_note(cls.customer, [{"item_code": cls.item, "serial_no": "WF-SN-1"}]).name
		cls.job = (
			frappe.get_doc(
				{
					"doctype": JOB,
					"job_type": "Installation",
					"company": fx.COMPANY,
					"source_doctype": "Delivery Note",
					"source_name": note,
					"assigned_technician": cls.users["tech"],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
		# Requests run on a separate DB connection and only see committed data.
		frappe.db.commit()  # nosemgrep
		cls.sids = {key: login_sid(user) for key, user in cls.users.items()}
		frappe.db.commit()  # nosemgrep
		cls.client = get_test_client(use_cookies=False)

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		fx.purge(
			names={
				JOB: [cls.job],
				"DeployOps Equipment Access Profile": list(cls.users.values()),
				"DeployOps Equipment Category": ["_Wf Cash"],
				"User": list(cls.users.values()),
				"Customer": [cls.customer],
				"Item": [cls.item],
			}
		)
		# Remove the committed fixtures so no test data stays on the site.
		frappe.db.commit()  # nosemgrep
		super().tearDownClass()

	def call(self, http_method, method, data, who=None):
		url = get_url(f"/api/method/deployops.api.jobs.{method}")
		payload = {**data, **({"sid": self.sids[who]} if who else {})}
		target = self.client.post if http_method == "POST" else self.client.get
		kwargs = {"data": payload} if http_method == "POST" else {"query_string": payload}
		return make_request(target=target, args=(url,), kwargs=kwargs)

	def test_workflow_over_http(self):
		job = {"job": self.job}
		# state-changing methods refuse GET
		self.assertNotEqual(
			self.call("GET", "job_action", {**job, "action": "start"}, "sup").status_code, 200
		)
		# guests and other technicians are refused
		self.assertEqual(self.call("POST", "job_action", {**job, "action": "start"}).status_code, 403)
		self.assertEqual(self.call("GET", "get_actions", job, "other").status_code, 403)
		# wrong state is a validation error, wrong person a permission error
		self.assertEqual(
			self.call("POST", "job_action", {**job, "action": "arrive"}, "tech").status_code, 417
		)
		self.assertEqual(self.call("POST", "job_action", {**job, "action": "start"}, "tech").status_code, 403)
		# the real path
		self.assertEqual(self.call("POST", "job_action", {**job, "action": "start"}, "sup").status_code, 200)
		self.assertEqual(
			self.call("POST", "job_action", {**job, "action": "arrive"}, "tech").status_code, 200
		)
		actions = json.loads(self.call("GET", "get_actions", job, "tech").data)["message"]
		device = next(iter(actions["devices"]))
		for action in ("start", "complete"):
			response = self.call("POST", "device_action", {**job, "device": device, "action": action}, "tech")
			self.assertEqual(response.status_code, 200)
		self.assertEqual(
			self.call("POST", "job_action", {**job, "action": "submit"}, "tech").status_code, 200
		)
		self.assertEqual(
			self.call("POST", "job_action", {**job, "action": "return"}, "sup").status_code, 417
		)  # no reason
		response = self.call("POST", "job_action", {**job, "action": "approve"}, "sup")
		self.assertEqual((response.status_code, json.loads(response.data)["message"]), (200, "Completed"))
