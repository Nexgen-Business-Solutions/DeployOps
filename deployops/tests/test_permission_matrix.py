import frappe
from frappe.desk.desktop import Workspace
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user

from deployops.roles import ALL_ROLES, DESK_ACCESS, SUPERVISOR, TECHNICIAN
from deployops.security.matrix import (
	DOCTYPE_MATRIX,
	ERPNEXT_DENIED,
	PTYPES,
	SUPPLIER_NAMES,
	WORKSPACE_ROLES,
	allowed,
	erpnext_allowed,
)
from deployops.tests.utils import make_role_user


class TestRoles(IntegrationTestCase):
	def setUp(self):
		self.addCleanup(frappe.db.rollback)
		from deployops.install import create_roles

		create_roles()

	def test_roles_exist_with_desk_access(self):
		for role, desk_access in DESK_ACCESS.items():
			with self.subTest(role=role):
				self.assertTrue(frappe.db.exists("Role", role))
				self.assertEqual(frappe.db.get_value("Role", role, "desk_access"), desk_access)

	def test_role_names_are_not_supplier_specific(self):
		names = set(ALL_ROLES) | set(
			frappe.get_all("Role", filters={"name": ["like", "DeployOps%"]}, pluck="name")
		)
		for name in names:
			for supplier in SUPPLIER_NAMES:
				self.assertNotIn(supplier, name.lower())

	def test_roles_are_assignable_to_any_user(self):
		for role in ALL_ROLES:
			with self.subTest(role=role):
				self.assertIn(role, frappe.get_roles(make_role_user(role)))

	def test_technician_has_no_desk(self):
		for role in ALL_ROLES:
			with self.subTest(role=role):
				user_type = frappe.db.get_value("User", make_role_user(role), "user_type")
				expected = "Website User" if role == TECHNICIAN else "System User"
				self.assertEqual(user_type, expected)


class TestRoleDrift(IntegrationTestCase):
	def setUp(self):
		# Ensure correct desk_access and user_type are committed before the test corrupts them;
		# rollback then restores this committed state, not whatever crashed run left behind.
		from deployops.install import create_roles

		create_roles()
		for role in DESK_ACCESS:
			make_role_user(role)  # fixes user_type if a previous run committed it wrong
		frappe.db.commit()  # nosemgrep
		self.addCleanup(frappe.db.rollback)
		self.addCleanup(frappe.clear_cache)

	def test_migrate_sets_changed_desk_access_back(self):
		"""#35 review: a Technician role given Desk access on a site is corrected by the next migrate."""
		from deployops.install import create_roles

		technician = make_role_user(TECHNICIAN)
		frappe.db.set_value("Role", TECHNICIAN, "desk_access", 1)
		frappe.db.set_value("Role", SUPERVISOR, "desk_access", 0)
		frappe.clear_cache()
		frappe.get_doc("User", technician).save(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("User", technician, "user_type"), "System User")  # the drift

		create_roles()  # what before_migrate runs

		for role, desk_access in DESK_ACCESS.items():
			with self.subTest(role=role):
				self.assertEqual(frappe.db.get_value("Role", role, "desk_access"), desk_access)
		self.assertEqual(frappe.db.get_value("User", technician, "user_type"), "Website User")


class TestPermissionMatrix(IntegrationTestCase):
	def setUp(self):
		# Clear permission cache and roll back so each test starts from the committed DB state.
		# TestRoleDrift (runs just before this class) temporarily promotes roles; without this
		# setUp its frappe.clear_cache cleanup still leaves role_permissions warm in frappe.local.
		frappe.local.role_permissions = {}
		self.addCleanup(frappe.db.rollback)
		self.addCleanup(frappe.clear_cache)

	def test_every_deployops_doctype_is_in_matrix(self):
		doctypes = frappe.get_all("DocType", filters={"module": "DeployOps", "istable": 0}, pluck="name")
		missing = sorted(set(doctypes) - set(DOCTYPE_MATRIX))
		self.assertEqual(missing, [], "Add these DocTypes to deployops/security/matrix.py")

	def test_every_deployops_doctype_checks_the_print_right(self):
		from deployops.hooks import PRINT_CHECKED

		doctypes = frappe.get_all("DocType", filters={"module": "DeployOps", "istable": 0}, pluck="name")
		self.assertEqual(
			sorted(set(doctypes) - set(PRINT_CHECKED)), [], "Add these to PRINT_CHECKED in hooks.py"
		)

	def test_doctype_rights_match_matrix(self):
		existing = [dt for dt in DOCTYPE_MATRIX if frappe.db.exists("DocType", dt)]
		for role in ALL_ROLES:
			user = make_role_user(role)
			for doctype in existing:
				if frappe.get_meta(doctype).istable:
					continue
				for ptype in PTYPES.values():
					with self.subTest(role=role, doctype=doctype, ptype=ptype):
						self.assertEqual(
							bool(frappe.has_permission(doctype, ptype, user=user)),
							allowed(doctype, role, ptype),
						)

	def test_erpnext_records_are_denied(self):
		for role in ALL_ROLES:
			user = make_role_user(role)
			for doctype in ERPNEXT_DENIED:
				for ptype in ("read", "write", "create", "delete", "print", "export"):
					with self.subTest(role=role, doctype=doctype, ptype=ptype):
						self.assertEqual(
							bool(frappe.has_permission(doctype, ptype, user=user)),
							erpnext_allowed(doctype, role, ptype),
						)

	def test_workspace_visible_only_to_desk_roles(self):
		for role in ALL_ROLES:
			with self.subTest(role=role), set_user(make_role_user(role)):
				permitted = bool(Workspace({"name": "DeployOps"}, minimal=True).is_permitted())
				self.assertEqual(permitted, role in WORKSPACE_ROLES)
