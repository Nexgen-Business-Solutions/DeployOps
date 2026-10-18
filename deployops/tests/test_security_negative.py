"""Negative security tests over HTTP (#35).

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
from deployops.roles import ALL_ROLES
from deployops.security.matrix import ERPNEXT_DENIED, erpnext_allowed
from deployops.tests.utils import make_role_user

TEST_CUSTOMER = "DeployOps Test Customer"


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
		cls.users = {role: make_role_user(role) for role in ALL_ROLES}
		if not frappe.db.exists("Customer", TEST_CUSTOMER):
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
		frappe.delete_doc("Customer", TEST_CUSTOMER, force=True, ignore_permissions=True)
		for user in cls.users.values():
			frappe.delete_doc("User", user, force=True, ignore_permissions=True)
		# Remove the committed fixtures so no test data stays on the site.
		frappe.db.commit()  # nosemgrep
		super().tearDownClass()

	def request(self, path: str, params: dict | None = None):
		return make_request(
			target=self.client.get, args=(get_url(path),), kwargs={"query_string": params or {}}
		)

	def test_guest_is_redirected_to_login(self):
		response = self.request("/")
		self.assertEqual(response.status_code, 302)
		self.assertTrue(response.location.startswith("/login"))

	def test_guest_cannot_read_erpnext_records(self):
		for doctype in ERPNEXT_DENIED:
			with self.subTest(doctype=doctype):
				self.assertEqual(self.request(f"/api/resource/{doctype}").status_code, 403)

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
