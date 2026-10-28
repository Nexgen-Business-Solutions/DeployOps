import frappe
from frappe.tests import IntegrationTestCase

from deployops.roles import ADMINISTRATOR, MANAGER, SUPERVISOR, TECHNICIAN
from deployops.security.equipment_access import (
	CATEGORY,
	PROFILE,
	get_allowed_categories,
	get_allowed_items,
	get_category_items,
	has_equipment_access,
	is_unrestricted,
)
from deployops.tests.utils import make_role_user


def make_item_group(name: str, parent: str = "All Item Groups") -> str:
	if not frappe.db.exists("Item Group", name):
		frappe.get_doc(
			{"doctype": "Item Group", "item_group_name": name, "parent_item_group": parent, "is_group": 1}
		).insert(ignore_permissions=True)
	return name


def make_item(code: str, item_group: str = "Products", serialized: bool = True) -> str:
	if not frappe.db.exists("Item", code):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": code,
				"item_group": item_group,
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"has_serial_no": int(serialized),
			}
		).insert(ignore_permissions=True)
	return code


def make_category(name: str, items=(), item_groups=(), enabled: bool = True):
	return frappe.get_doc(
		{
			"doctype": CATEGORY,
			"category_name": name,
			"enabled": int(enabled),
			"items": [{"item_code": code} for code in items],
			"item_groups": [{"item_group": group} for group in item_groups],
		}
	).insert(ignore_permissions=True)


def make_profile(user: str, categories=(), enabled: bool = True):
	return frappe.get_doc(
		{
			"doctype": PROFILE,
			"user": user,
			"enabled": int(enabled),
			"categories": [{"category": category} for category in categories],
		}
	).insert(ignore_permissions=True)


class TestEquipmentAccess(IntegrationTestCase):
	def setUp(self):
		# Each test starts clean: roll back its records and the Stock Setting below afterwards.
		self.addCleanup(frappe.db.rollback)
		# ERPNext v16 refuses serial-numbered Items unless this Stock Setting is on.
		frappe.db.set_single_value("Stock Settings", "enable_serial_and_batch_no_for_item", 1)
		self.recycler = make_item("_Test Cash Recycler")
		self.robot = make_item("_Test Service Robot")
		self.spare = make_item("_Test Spare Part", serialized=False)
		self.technician = make_role_user(TECHNICIAN)

	def test_category_rejects_non_serialized_item(self):
		with self.assertRaises(frappe.ValidationError):
			make_category("_Test Bad Category", items=[self.spare])

	def test_category_rejects_duplicate_rows(self):
		with self.assertRaises(frappe.ValidationError):
			make_category("_Test Dup Items", items=[self.recycler, self.recycler])
		with self.assertRaises(frappe.ValidationError):
			make_category("_Test Dup Groups", item_groups=["Products", "Products"])

	def test_profile_rejects_duplicate_categories(self):
		make_category("_Test Cash", items=[self.recycler])
		with self.assertRaises(frappe.ValidationError):
			make_profile(self.technician, ["_Test Cash", "_Test Cash"])

	def test_one_profile_per_user(self):
		make_profile(self.technician)
		with self.assertRaises(frappe.DuplicateEntryError):
			make_profile(self.technician)

	def test_user_without_profile_gets_nothing(self):
		make_category("_Test Cash", items=[self.recycler])
		self.assertEqual(get_allowed_categories(self.technician), [])
		self.assertEqual(get_allowed_items(self.technician), set())
		self.assertFalse(has_equipment_access(self.recycler, self.technician))

	def test_profile_grants_only_its_categories(self):
		make_category("_Test Cash", items=[self.recycler])
		make_category("_Test Robots", items=[self.robot])
		make_profile(self.technician, ["_Test Cash"])

		self.assertEqual(get_allowed_categories(self.technician), ["_Test Cash"])
		self.assertTrue(has_equipment_access(self.recycler, self.technician))
		self.assertFalse(has_equipment_access(self.robot, self.technician))

	def test_multiple_and_overlapping_categories(self):
		make_category("_Test Cash", items=[self.recycler])
		make_category("_Test All Machines", items=[self.recycler, self.robot])
		make_profile(self.technician, ["_Test Cash", "_Test All Machines"])

		self.assertEqual(get_allowed_items(self.technician), {self.recycler, self.robot})

	def test_item_group_includes_subgroups_and_only_serialized_items(self):
		parent = make_item_group("_Test Machines")
		child = make_item_group("_Test Robots Group", parent=parent)
		robot = make_item("_Test Group Robot", item_group=child)
		make_item("_Test Group Spare", item_group=child, serialized=False)
		make_category("_Test By Group", item_groups=[parent])
		make_profile(self.technician, ["_Test By Group"])

		self.assertEqual(get_allowed_items(self.technician), {robot})

	def test_disabled_category_grants_nothing(self):
		make_category("_Test Cash", items=[self.recycler], enabled=False)
		make_profile(self.technician, ["_Test Cash"])
		self.assertFalse(has_equipment_access(self.recycler, self.technician))

	def test_disabled_profile_grants_nothing(self):
		make_category("_Test Cash", items=[self.recycler])
		make_profile(self.technician, ["_Test Cash"], enabled=False)
		self.assertFalse(has_equipment_access(self.recycler, self.technician))

	def test_revocation_is_immediate(self):
		make_category("_Test Cash", items=[self.recycler])
		profile = make_profile(self.technician, ["_Test Cash"])
		self.assertTrue(has_equipment_access(self.recycler, self.technician))

		profile.categories = []
		profile.save(ignore_permissions=True)
		self.assertFalse(has_equipment_access(self.recycler, self.technician))

	def test_profiles_restrict_supervisor_and_manager(self):
		make_category("_Test Cash", items=[self.recycler])
		for role in (SUPERVISOR, MANAGER):
			with self.subTest(role=role):
				self.assertFalse(has_equipment_access(self.recycler, make_role_user(role)))

	def test_profile_needs_an_operational_role(self):
		"""#11 review: a profile alone grants nothing; the user needs a Technician, Supervisor or
		Manager role."""
		make_category("_Test Cash", items=[self.recycler])
		user = "_test-no-role@deployops.test"
		frappe.get_doc(
			{"doctype": "User", "email": user, "first_name": "No role", "send_welcome_email": 0}
		).insert(ignore_permissions=True)
		make_profile(user, ["_Test Cash"])
		self.assertEqual(get_allowed_categories(user), [])
		self.assertFalse(has_equipment_access(self.recycler, user))

	def test_revoking_the_role_revokes_the_equipment(self):
		make_category("_Test Cash", items=[self.recycler])
		make_profile(self.technician, ["_Test Cash"])
		self.assertTrue(has_equipment_access(self.recycler, self.technician))

		self.addCleanup(
			frappe.clear_cache, user=self.technician
		)  # cached roles; the rollback restores the row
		user = frappe.get_doc("User", self.technician)
		user.roles = []
		user.save(ignore_permissions=True)
		self.assertEqual(get_allowed_categories(self.technician), [])
		self.assertFalse(has_equipment_access(self.recycler, self.technician))

	def test_disabled_users_get_nothing(self):
		make_category("_Test Cash", items=[self.recycler])
		make_profile(self.technician, ["_Test Cash"])
		admin = make_role_user(ADMINISTRATOR)
		for user in (self.technician, admin):
			self.addCleanup(frappe.clear_document_cache, "User", user)
			frappe.db.set_value("User", user, "enabled", 0)
			frappe.clear_document_cache("User", user)
			with self.subTest(user=user):
				self.assertEqual(get_allowed_categories(user), [])
				self.assertEqual(get_allowed_items(user), set())
				self.assertFalse(is_unrestricted(user))

	def test_mapped_item_that_lost_its_serial_numbers_is_left_out(self):
		make_category("_Test Cash", items=[self.recycler, self.robot])
		make_profile(self.technician, ["_Test Cash"])
		frappe.db.set_value("Item", self.robot, "has_serial_no", 0)  # changed after mapping
		self.assertEqual(get_allowed_items(self.technician), {self.recycler})
		self.assertEqual(get_category_items(["_Test Cash"]), {self.recycler})

	def test_admin_sees_all_serialized_equipment(self):
		admin = make_role_user(ADMINISTRATOR)
		allowed = get_allowed_items(admin)
		self.assertIn(self.recycler, allowed)
		self.assertIn(self.robot, allowed)
		self.assertNotIn(self.spare, allowed)
