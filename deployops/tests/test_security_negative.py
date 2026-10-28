"""Negative security tests over HTTP

Requests go through Frappe's WSGI app in a separate thread with its own DB connection, so the
fixtures here are committed and removed again in tearDownClass.
"""

import importlib
import pkgutil

import frappe
from frappe.auth import CookieManager, LoginManager
from frappe.tests import IntegrationTestCase
from frappe.tests.test_api import make_request
from frappe.utils import get_test_client, get_url, set_request

import deployops
from deployops.roles import ALL_ROLES, TECHNICIAN
from deployops.security.matrix import DOCTYPE_MATRIX, ERPNEXT_DENIED, allowed, erpnext_allowed
from deployops.tests.utils import make_role_user, role_user_email

# Unique per run: the tests create it and delete only what they created.
TEST_CUSTOMER = f"DeployOps Test Customer {frappe.generate_hash(length=6)}"


def login_sid(user: str) -> str:
	set_request(path="/")
	frappe.local.cookie_manager = CookieManager()
	frappe.local.login_manager = LoginManager()
	frappe.local.login_manager.login_as(user)
	sid = frappe.session.sid
	frappe.set_user("Administrator")
	return sid


class TestSecurityNegative(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.client = get_test_client(use_cookies=False)
		# Delete in teardown only the users this class created (make_role_user reuses existing ones).
		cls.created_users = [r for r in ALL_ROLES if not frappe.db.exists("User", role_user_email(r))]
		cls.users = {role: make_role_user(role) for role in ALL_ROLES}
		cls.created_customer = not frappe.db.exists("Customer", TEST_CUSTOMER)
		if cls.created_customer:
			frappe.get_doc({"doctype": "Customer", "customer_name": TEST_CUSTOMER}).insert(
				ignore_permissions=True, ignore_mandatory=True
			)
		# Requests run on a separate DB connection and only see committed users and records.
		frappe.db.commit()  # nosemgrep
		cls.sids = {role: login_sid(user) for role, user in cls.users.items()}
		frappe.db.commit()  # nosemgrep

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		if cls.created_customer:
			frappe.delete_doc("Customer", TEST_CUSTOMER, force=True, ignore_permissions=True)
		for user in (cls.users[role] for role in cls.created_users):
			frappe.delete_doc("User", user, force=True, ignore_permissions=True)
		# Remove the committed fixtures so no test data stays on the site.
		frappe.db.commit()  # nosemgrep
		super().tearDownClass()

	def request(self, path: str, params: dict | None = None):
		return make_request(
			target=self.client.get, args=(get_url(path),), kwargs={"query_string": params or {}}
		)

	def test_guest_gets_only_the_app_shell(self):
		# The React app (under /deployops) shows its own login screen; the shell holds no data and
		# no session token, also on a deep link.
		for path in ("/deployops", "/deployops/job/JOB-0001"):
			with self.subTest(path=path):
				response = self.request(path)
				self.assertEqual(response.status_code, 200)
				body = response.data.decode()
				self.assertIn('id="root"', body)
				for leak in (TEST_CUSTOMER, "@deployops.test"):
					self.assertNotIn(leak, body)
				self.assertIn("window.csrf_token = '';", body)  # guests get no session token
		for method in ("me", "home", "my_jobs"):
			with self.subTest(method=method):
				params = {"card": "cashmatic-onsite"} if method == "my_jobs" else None
				self.assertEqual(
					self.request(f"/api/method/deployops.api.technician.{method}", params).status_code, 403
				)

	def test_site_root_sends_only_technicians_to_the_app(self):
		"""DeployOps doesn't claim "/": guests get Frappe's login page; a Technician, whose home page is
		the app, is redirected to /deployops; Desk roles keep their own home."""
		guest = self.request("/")
		self.assertEqual(guest.status_code, 200)
		self.assertIn("<title>Login</title>", guest.data.decode())
		for role in ALL_ROLES:
			with self.subTest(role=role):
				response = self.request("/", {"sid": self.sids[role]})
				location = response.headers.get("Location") or ""
				if role == TECHNICIAN:
					self.assertEqual((response.status_code, location.endswith("/deployops")), (302, True))
				else:
					self.assertFalse(location.endswith("/deployops"))

	def test_guest_cannot_read_erpnext_records(self):
		for doctype in ERPNEXT_DENIED:
			with self.subTest(doctype=doctype):
				self.assertEqual(self.request(f"/api/resource/{doctype}").status_code, 403)

	def test_deployops_doctype_api_follows_matrix(self):
		existing = [
			dt for dt in DOCTYPE_MATRIX if frappe.db.exists("DocType", dt) and not frappe.get_meta(dt).istable
		]

		def url(doctype):  # a Single DocType has no list: read its one document
			return f"/api/resource/{doctype}" + (f"/{doctype}" if frappe.get_meta(doctype).issingle else "")

		for role, sid in self.sids.items():
			for doctype in existing:
				with self.subTest(role=role, doctype=doctype):
					response = self.request(url(doctype), {"sid": sid})
					self.assertEqual(response.status_code, 200 if allowed(doctype, role, "read") else 403)

		for doctype in existing:
			with self.subTest(guest=True, doctype=doctype):
				self.assertEqual(self.request(url(doctype)).status_code, 403)

	def test_guest_cannot_call_source_lookups(self):
		for method, params in (
			("get_source_summary", {"doctype": "Sales Order", "name": "x"}),
			("search_sources", {"doctype": "Sales Order"}),
			("get_serial", {"serial_no": "x"}),
		):
			with self.subTest(method=method):
				response = self.request(f"/api/method/deployops.api.sources.{method}", params)
				self.assertEqual(response.status_code, 403)

	def test_roles_cannot_list_erpnext_records(self):
		for role, sid in self.sids.items():
			for doctype in ERPNEXT_DENIED:
				with self.subTest(role=role, doctype=doctype):
					response = self.request(f"/api/resource/{doctype}", {"sid": sid})
					# Item listing is the accepted ERPNext "Desk User" default (see matrix.py).
					expected = 200 if erpnext_allowed(doctype, role, "select") else 403
					self.assertEqual(response.status_code, expected)

	def test_roles_cannot_open_erpnext_record_by_url(self):
		for role, sid in self.sids.items():
			with self.subTest(role=role):
				response = self.request(f"/api/resource/Customer/{TEST_CUSTOMER}", {"sid": sid})
				self.assertEqual(response.status_code, 403)

				response = self.request(
					"/api/method/frappe.client.get",
					{"doctype": "Customer", "name": TEST_CUSTOMER, "sid": sid},
				)
				self.assertEqual(response.status_code, 403)

	def test_roles_cannot_print_erpnext_record(self):
		for role, sid in self.sids.items():
			with self.subTest(role=role):
				response = self.request(
					"/printview", {"doctype": "Customer", "name": TEST_CUSTOMER, "sid": sid}
				)
				self.assertNotEqual(response.status_code, 200)

	def test_no_deployops_method_is_open_to_guests(self):
		for module in pkgutil.walk_packages(deployops.__path__, "deployops."):
			if ".tests" not in module.name:
				importlib.import_module(module.name)

		open_methods = sorted(
			f"{fn.__module__}.{fn.__name__}"
			for fn in frappe.guest_methods
			if getattr(fn, "__module__", "").startswith("deployops.")
		)
		self.assertEqual(open_methods, [])
