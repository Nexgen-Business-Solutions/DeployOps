from frappe.tests import UnitTestCase

from deployops.checklists.cards import FORM_DOCTYPES as CHECKLIST_FORMS
from deployops.roles import ADMINISTRATOR, ALIASES, ALL_ROLES, DESK_ACCESS, MANAGER, SUPERVISOR, TECHNICIAN
from deployops.security.matrix import (
	DESK_ROLES,
	DOCTYPE_MATRIX,
	PTYPES,
	WORKSPACE_ROLES,
	allowed,
	erpnext_allowed,
)

VALID_LETTERS = set(PTYPES) | {"a"}
NO_DELETE = ("DeployOps Job", *CHECKLIST_FORMS, "DeployOps Equipment Allocation")


class TestRolesUnit(UnitTestCase):
	def test_aliases_and_desk_access_cover_the_same_roles(self):
		self.assertEqual(set(ALIASES), set(DESK_ACCESS))
		self.assertEqual(set(ALL_ROLES), {TECHNICIAN, SUPERVISOR, MANAGER, ADMINISTRATOR})

	def test_only_technician_has_no_desk(self):
		self.assertEqual([role for role, desk in DESK_ACCESS.items() if not desk], [TECHNICIAN])
		self.assertEqual(set(DESK_ROLES), {SUPERVISOR, MANAGER, ADMINISTRATOR})
		self.assertEqual(set(WORKSPACE_ROLES), set(DESK_ROLES))


class TestMatrixUnit(UnitTestCase):
	def test_every_row_covers_every_role(self):
		for doctype, row in DOCTYPE_MATRIX.items():
			with self.subTest(doctype=doctype):
				self.assertEqual(set(row), set(ALL_ROLES))

	def test_only_valid_letters(self):
		for doctype, row in DOCTYPE_MATRIX.items():
			for role, letters in row.items():
				with self.subTest(doctype=doctype, role=role):
					self.assertLessEqual(set(letters), VALID_LETTERS)
					self.assertEqual(len(letters), len(set(letters)), "duplicate letter")

	def test_no_delete_on_operational_records(self):
		for doctype in NO_DELETE:
			for role in ALL_ROLES:
				with self.subTest(doctype=doctype, role=role):
					self.assertFalse(allowed(doctype, role, "delete"))

	def test_only_manager_and_admin_export(self):
		for doctype in DOCTYPE_MATRIX:
			for role in (TECHNICIAN, SUPERVISOR):
				with self.subTest(doctype=doctype, role=role):
					self.assertFalse(allowed(doctype, role, "export"))

	def test_admin_does_not_approve(self):
		for doctype, row in DOCTYPE_MATRIX.items():
			with self.subTest(doctype=doctype):
				self.assertNotIn("a", row[ADMINISTRATOR])

	def test_allowed_maps_letters_to_ptypes(self):
		self.assertTrue(allowed("DeployOps Job", SUPERVISOR, "read"))
		self.assertTrue(allowed("DeployOps Job", SUPERVISOR, "create"))
		self.assertFalse(allowed("DeployOps Job", SUPERVISOR, "delete"))
		self.assertFalse(allowed("DeployOps Job", TECHNICIAN, "create"))
		self.assertFalse(allowed("DeployOps Equipment Category", TECHNICIAN, "read"))
		# "a" is a workflow transition, never a DocPerm ptype
		self.assertFalse(allowed("DeployOps Job", SUPERVISOR, "approve"))

	def test_erpnext_allowed_only_item_defaults_for_desk_roles(self):
		for ptype in ("select", "print", "export", "report"):
			with self.subTest(ptype=ptype):
				self.assertFalse(erpnext_allowed("Item", TECHNICIAN, ptype))
				for role in DESK_ROLES:
					self.assertTrue(erpnext_allowed("Item", role, ptype))

		for role in ALL_ROLES:
			with self.subTest(role=role):
				self.assertFalse(erpnext_allowed("Item", role, "read"))
				self.assertFalse(erpnext_allowed("Item", role, "write"))
				self.assertFalse(erpnext_allowed("Customer", role, "select"))
