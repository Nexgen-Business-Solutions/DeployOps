import frappe
from frappe.desk.desktop import Workspace
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user

NO_ROLE_USER = "deployops-no-role@example.com"


class TestInstall(IntegrationTestCase):
	def test_app_is_installed(self):
		self.assertIn("deployops", frappe.get_installed_apps())

	def test_erpnext_is_required_and_installed(self):
		self.assertIn("erpnext", frappe.get_hooks("required_apps", app_name="deployops"))
		self.assertIn("erpnext", frappe.get_installed_apps())

	def test_module_belongs_to_app(self):
		self.assertEqual(frappe.db.get_value("Module Def", "DeployOps", "app_name"), "deployops")

	def test_workspace_is_restricted_to_system_manager(self):
		workspace = frappe.get_doc("Workspace", "DeployOps")
		self.assertEqual(workspace.module, "DeployOps")
		self.assertEqual([d.role for d in workspace.roles], ["System Manager"])

	def test_workspace_hidden_from_user_without_role(self):
		if not frappe.db.exists("User", NO_ROLE_USER):
			frappe.get_doc(
				{"doctype": "User", "email": NO_ROLE_USER, "first_name": "No Role", "send_welcome_email": 0}
			).insert(ignore_permissions=True)

		with set_user(NO_ROLE_USER):
			self.assertFalse(Workspace({"name": "DeployOps"}, minimal=True).is_permitted())

		with set_user("Administrator"):
			self.assertTrue(Workspace({"name": "DeployOps"}, minimal=True).is_permitted())
