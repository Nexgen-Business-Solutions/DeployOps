"""Job-level visibility (#12): role + equipment profile + assignment, with no way around it."""

import json

import frappe
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user
from frappe.tests.test_api import make_request
from frappe.utils import get_test_client, get_url

from deployops.roles import ADMINISTRATOR, ALIASES, MANAGER, SUPERVISOR, TECHNICIAN
from deployops.tests import erpnext_fixtures as fx
from deployops.tests.test_security_negative import login_sid

JOB = "DeployOps Job"


def make_vis_user(role: str) -> str:
	email = f"vis-{ALIASES[role].lower()}@deployops.test"
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": ALIASES[role],
				"send_welcome_email": 0,
				"roles": [{"role": role}],
			}
		).insert(ignore_permissions=True)
	return email


def setup_world(test):
	"""Items, two categories, a customer, sources and four jobs: cash, robot, mixed, no machines."""
	fx.make_company()
	test.cash, test.robot = fx.make_item("_Vis CR-460"), fx.make_item("_Vis BB-PRO")
	test.customer = fx.make_customer("_VisCust")
	for name, item in (("_Vis Cash", test.cash), ("_Vis Robots", test.robot)):
		if not frappe.db.exists("DeployOps Equipment Category", name):
			frappe.get_doc(
				{
					"doctype": "DeployOps Equipment Category",
					"category_name": name,
					"items": [{"item_code": item}],
				}
			).insert(ignore_permissions=True)

	# Own users: other test classes create and delete the shared role users.
	test.users = {role: make_vis_user(role) for role in (TECHNICIAN, SUPERVISOR, MANAGER, ADMINISTRATOR)}
	for role in (TECHNICIAN, SUPERVISOR, MANAGER):
		if frappe.db.exists("DeployOps Equipment Access Profile", test.users[role]):
			continue
		frappe.get_doc(
			{
				"doctype": "DeployOps Equipment Access Profile",
				"user": test.users[role],
				"categories": [{"category": "_Vis Cash"}],
			}
		).insert(ignore_permissions=True)

	def job(items, **fields):
		order = fx.make_sales_order(test.customer, items).name
		return (
			frappe.get_doc(
				{
					"doctype": JOB,
					"job_type": "Pre-installation",
					"company": fx.COMPANY,
					"source_doctype": "Sales Order",
					"source_name": order,
					**fields,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	test.cash_job = job([test.cash], assigned_technician=test.users[TECHNICIAN])
	test.robot_job = job([test.robot])
	test.mixed_job = job([test.cash, test.robot])
	subscription = fx.make_subscription(test.customer).name

	def empty_job(category=None):
		return (
			frappe.get_doc(
				{
					"doctype": JOB,
					"job_type": "Pre-installation",
					"company": fx.COMPANY,
					"source_doctype": "Subscription",
					"source_name": subscription,
					"equipment_category": category,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	test.empty_job = empty_job()
	test.empty_cash_job = empty_job("_Vis Cash")
	test.empty_robot_job = empty_job("_Vis Robots")
	test.all_jobs = {
		test.cash_job,
		test.robot_job,
		test.mixed_job,
		test.empty_job,
		test.empty_cash_job,
		test.empty_robot_job,
	}


class TestJobScope(IntegrationTestCase):
	def setUp(self):
		self.addCleanup(frappe.db.rollback)
		setup_world(self)

	def visible(self, role):
		with set_user(self.users[role]):
			return set(frappe.get_list(JOB, pluck="name")) & self.all_jobs

	def test_supervisor_and_manager_see_only_their_equipment(self):
		expected = {self.cash_job, self.empty_job, self.empty_cash_job}
		for role in (SUPERVISOR, MANAGER):
			with self.subTest(role=role):
				self.assertEqual(self.visible(role), expected)

	def test_admin_sees_every_job(self):
		self.assertEqual(self.visible(ADMINISTRATOR), self.all_jobs)

	def test_technician_sees_only_assigned(self):
		self.assertEqual(self.visible(TECHNICIAN), {self.cash_job})

	def test_document_access_matches_the_list(self):
		with set_user(self.users[SUPERVISOR]):
			self.assertTrue(frappe.has_permission(JOB, "read", self.cash_job))
			for job in (self.robot_job, self.mixed_job, self.empty_robot_job):
				with self.subTest(job=job):
					self.assertFalse(frappe.has_permission(JOB, "read", job))
					with self.assertRaises(frappe.PermissionError):
						frappe.get_doc(JOB, job).check_permission("read")

	def test_revoking_a_category_hides_its_jobs_immediately(self):
		profile = frappe.get_doc("DeployOps Equipment Access Profile", self.users[SUPERVISOR])
		profile.categories = []
		profile.save(ignore_permissions=True)
		self.assertEqual(self.visible(SUPERVISOR), {self.empty_job})

	def test_user_without_deployops_role_sees_nothing(self):
		outsider = "_vis-outsider@deployops.test"
		frappe.get_doc(
			{
				"doctype": "User",
				"email": outsider,
				"first_name": "Out",
				"send_welcome_email": 0,
				"roles": [{"role": "Sales User"}],
			}
		).insert(ignore_permissions=True)
		with set_user(outsider):
			self.assertFalse(frappe.has_permission(JOB, "read", self.cash_job))


class TestJobScopeOverHttp(IntegrationTestCase):
	"""Every way of reaching a job a Supervisor may not see, over real HTTP requests."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		setup_world(cls)
		# Different contents: Frappe de-duplicates identical files onto one stored path.
		for job, name in ((cls.cash_job, "_vis_cash.txt"), (cls.robot_job, "_vis_robot.txt")):
			frappe.get_doc(
				{
					"doctype": "File",
					"file_name": name,
					"content": f"photo of {job}".encode(),
					"is_private": 1,
					"attached_to_doctype": JOB,
					"attached_to_name": job,
				}
			).insert(ignore_permissions=True)
		cls.files = {
			job: frappe.db.get_value("File", {"attached_to_name": job}, ["name", "file_url"], as_dict=True)
			for job in (cls.cash_job, cls.robot_job)
		}
		# Requests run on a separate DB connection and only see committed data.
		frappe.db.commit()  # nosemgrep
		cls.sid = login_sid(cls.users[SUPERVISOR])
		frappe.db.commit()  # nosemgrep
		cls.client = get_test_client(use_cookies=False)

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		fx.purge(
			names={
				"File": [f.name for f in cls.files.values()],
				JOB: sorted(cls.all_jobs),
				"DeployOps Equipment Access Profile": list(cls.users.values()),
				"DeployOps Equipment Category": ["_Vis Cash", "_Vis Robots"],
				"User": list(cls.users.values()),
				"Customer": [cls.customer],
				"Item": [cls.cash, cls.robot],
			}
		)
		# Remove the committed fixtures so no test data stays on the site.
		frappe.db.commit()  # nosemgrep
		super().tearDownClass()

	def get(self, path, params=None):
		return make_request(
			target=self.client.get,
			args=(get_url(path),),
			kwargs={"query_string": {**(params or {}), "sid": self.sid}},
		)

	def test_list_api_hides_out_of_scope_jobs(self):
		response = self.get(f"/api/resource/{JOB}", {"limit_page_length": 100})
		self.assertEqual(response.status_code, 200)
		names = {row["name"] for row in json.loads(response.data)["data"]}
		self.assertIn(self.cash_job, names)
		self.assertTrue(names.isdisjoint({self.robot_job, self.mixed_job, self.empty_robot_job}))

	def test_report_view_and_get_list_hide_out_of_scope_jobs(self):
		for path, params in (
			(
				"/api/method/frappe.desk.reportview.get",
				{"doctype": JOB, "fields": '["name"]', "page_length": 100},
			),
			("/api/method/frappe.client.get_list", {"doctype": JOB, "limit_page_length": 100}),
		):
			with self.subTest(path=path):
				response = self.get(path, params)
				self.assertEqual(response.status_code, 200)
				self.assertNotIn(self.robot_job, response.data.decode())
				self.assertIn(self.cash_job, response.data.decode())

	def test_link_search_hides_out_of_scope_jobs(self):
		response = self.get(
			"/api/method/frappe.desk.search.search_link", {"doctype": JOB, "txt": "", "page_length": 100}
		)
		self.assertEqual(response.status_code, 200)
		self.assertNotIn(self.robot_job, response.data.decode())

	def test_direct_url_api_and_print_refused(self):
		checks = (
			(f"/api/resource/{JOB}/{self.robot_job}", None),
			("/api/method/frappe.client.get", {"doctype": JOB, "name": self.robot_job}),
			("/api/method/frappe.desk.form.load.getdoc", {"doctype": JOB, "name": self.robot_job}),
		)
		for path, params in checks:
			with self.subTest(path=path):
				self.assertEqual(self.get(path, params).status_code, 403)
		# get_value runs through the permission-filtered list: 200, but nothing comes back.
		response = self.get(
			"/api/method/frappe.client.get_value",
			{"doctype": JOB, "filters": self.robot_job, "fieldname": "customer"},
		)
		self.assertFalse(json.loads(response.data).get("message"))

		response = self.get("/printview", {"doctype": JOB, "name": self.robot_job})
		self.assertNotEqual(response.status_code, 200)
		self.assertEqual(self.get(f"/api/resource/{JOB}/{self.cash_job}").status_code, 200)

	def test_private_attachments_follow_the_job(self):
		self.assertEqual(self.get(self.files[self.cash_job].file_url).status_code, 200)
		self.assertEqual(self.get(self.files[self.robot_job].file_url).status_code, 403)
		self.assertEqual(self.get(f"/api/resource/File/{self.files[self.robot_job].name}").status_code, 403)
