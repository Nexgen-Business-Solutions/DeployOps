import frappe
from frappe.desk.desktop import Workspace
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user

from deployops.security.matrix import WORKSPACE_ROLES

NO_ROLE_USER = "deployops-no-role@example.com"


class TestInstall(IntegrationTestCase):
	def test_app_is_installed(self):
		self.assertIn("deployops", frappe.get_installed_apps())

	def test_erpnext_is_required_and_installed(self):
		self.assertIn("erpnext", frappe.get_hooks("required_apps", app_name="deployops"))
		self.assertIn("erpnext", frappe.get_installed_apps())

	def test_module_belongs_to_app(self):
		self.assertEqual(frappe.db.get_value("Module Def", "DeployOps", "app_name"), "deployops")

	def test_workspace_is_restricted_to_desk_roles(self):
		workspace = frappe.get_doc("Workspace", "DeployOps")
		self.assertEqual(workspace.module, "DeployOps")
		self.assertEqual({d.role for d in workspace.roles}, set(WORKSPACE_ROLES))

	def test_workspace_hidden_from_user_without_role(self):
		if not frappe.db.exists("User", NO_ROLE_USER):
			frappe.get_doc(
				{"doctype": "User", "email": NO_ROLE_USER, "first_name": "No Role", "send_welcome_email": 0}
			).insert(ignore_permissions=True)

		with set_user(NO_ROLE_USER):
			self.assertFalse(Workspace({"name": "DeployOps"}, minimal=True).is_permitted())

		with set_user("Administrator"):
			self.assertTrue(Workspace({"name": "DeployOps"}, minimal=True).is_permitted())


class TestFrontendUrls(IntegrationTestCase):
	"""The React app (and its own sign-in screen) lives only under /deployops; other apps keep their URLs."""

	def setUp(self):
		frappe.clear_cache()  # website route rules are cached

	def resolve(self, path):
		"""Resolve as a real request does: Frappe only evaluates dynamic routes inside a request."""
		from frappe.website.path_resolver import resolve_path
		from werkzeug.test import EnvironBuilder
		from werkzeug.wrappers import Request

		previous = getattr(frappe.local, "request", None)
		frappe.local.request = Request(EnvironBuilder(path="/" + path).get_environ())
		try:
			return resolve_path(path)
		finally:
			frappe.local.request = previous

	def test_the_app_and_its_client_routes_resolve_to_the_deployops_page(self):
		for path in (
			"deployops",
			"deployops/c/cashmatic-installation",
			"deployops/job/JOB-0001",
			"deployops/form/X/Y",
		):
			with self.subTest(path):
				self.assertEqual(self.resolve(path), "deployops")

	def test_other_urls_are_left_to_frappe_and_other_apps(self):
		# each resolves to itself: no DeployOps catch-all takes them over
		for path in ("login", "update-password", "other-app", "other-app/page", "deployops-other"):
			with self.subTest(path):
				self.assertEqual(self.resolve(path), path)

	def test_the_site_root_is_not_claimed(self):
		self.assertNotIn("frontend", frappe.get_hooks("home_page", app_name="deployops"))
		self.assertNotIn("deployops", frappe.get_hooks("home_page", app_name="deployops"))


class TestOldUrlRedirects(IntegrationTestCase):
	"""Links from when the app owned the site root move to the same screen under /deployops."""

	def setUp(self):
		frappe.cache.delete_value("website_redirects")  # resolved redirects are cached per path
		self.addCleanup(frappe.cache.delete_value, "website_redirects")

	def redirect(self, path):
		"""(location, status) of the redirect for `path`, or None when it is not redirected."""
		from frappe.website.path_resolver import resolve_redirect

		frappe.flags.redirect_location = None
		try:
			resolve_redirect(path)
		except frappe.Redirect as redirect:
			return frappe.flags.redirect_location, redirect.http_status_code
		return None

	def test_old_screens_move_to_deployops(self):
		for path, target in (
			("", "/deployops"),
			("c/cashmatic-installation", "/deployops/c/cashmatic-installation"),
			("job/JOB-0001", "/deployops/job/JOB-0001"),
			(
				"form/DeployOps Cashmatic Installation/CI-0001",
				"/deployops/form/DeployOps Cashmatic Installation/CI-0001",
			),
		):
			with self.subTest(path):
				self.assertEqual(self.redirect(path), (target, 302))

	def test_other_urls_are_not_redirected(self):
		for path in ("deployops", "deployops/job/JOB-0001", "login", "update-password", "other-app", "jobs"):
			with self.subTest(path):
				self.assertIsNone(self.redirect(path))
