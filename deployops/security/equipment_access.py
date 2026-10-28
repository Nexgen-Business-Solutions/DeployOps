"""Equipment access profiles (#11 / #36): which equipment a user may work with.

Effective access = role (matrix.py) ∩ equipment profile (this module) ∩ job scope (#12).
Everything is read live from the database, so a revoked category stops working immediately.
DeployOps Administrators configure the categories and are not restricted by profiles.

A profile grants nothing on its own: the user must also be enabled and hold an operational
DeployOps role (Technician, Supervisor, Manager). So a profile left behind after a user is disabled
or loses their role stops working at once, whatever code asks.
"""

import frappe
from frappe.utils.nestedset import get_descendants_of

from deployops.roles import ADMINISTRATOR, MANAGER, SUPERVISOR, TECHNICIAN

CATEGORY = "DeployOps Equipment Category"
PROFILE = "DeployOps Equipment Access Profile"

# Roles whose equipment comes from a profile. Administrators are unrestricted instead.
PROFILE_ROLES = (TECHNICIAN, SUPERVISOR, MANAGER)


def is_enabled(user: str) -> bool:
	return user == "Administrator" or bool(frappe.get_cached_value("User", user, "enabled"))


def is_unrestricted(user: str) -> bool:
	if user == "Administrator":
		return True
	return is_enabled(user) and ADMINISTRATOR in frappe.get_roles(user)


def get_allowed_categories(user: str | None = None) -> list[str]:
	"""Enabled categories the user may work with."""
	user = user or frappe.session.user
	enabled = frappe.get_all(CATEGORY, filters={"enabled": 1}, pluck="name")
	if is_unrestricted(user):
		return enabled
	if not is_enabled(user) or not set(PROFILE_ROLES) & set(frappe.get_roles(user)):
		return []

	profile = frappe.db.get_value(PROFILE, {"user": user, "enabled": 1})
	if not profile:
		return []

	granted = frappe.get_all(
		f"{PROFILE} Category", filters={"parent": profile, "parenttype": PROFILE}, pluck="category"
	)
	return [category for category in enabled if category in set(granted)]


def get_allowed_items(user: str | None = None) -> set[str]:
	"""Serial-numbered Items (models) the user may work with."""
	user = user or frappe.session.user
	if is_unrestricted(user):
		return set(frappe.get_all("Item", filters={"has_serial_no": 1}, pluck="name"))

	return get_category_items(get_allowed_categories(user))


def get_category_items(categories: list[str]) -> set[str]:
	"""Serial-numbered Items in the given categories (explicit Items plus Item Groups and sub-groups).

	Explicit Items are checked against the Item again: one that stopped being serial-numbered after
	it was mapped is left out, like the Item Group members.
	"""
	if not categories:
		return set()

	mapped = frappe.get_all(
		f"{CATEGORY} Item",
		filters={"parent": ["in", categories], "parenttype": CATEGORY},
		pluck="item_code",
	)
	items = set(
		frappe.get_all("Item", filters={"name": ["in", mapped or [""]], "has_serial_no": 1}, pluck="name")
	)

	groups = set(
		frappe.get_all(
			f"{CATEGORY} Item Group",
			filters={"parent": ["in", categories], "parenttype": CATEGORY},
			pluck="item_group",
		)
	)
	for group in list(groups):
		groups.update(get_descendants_of("Item Group", group, ignore_permissions=True))
	if groups:
		items.update(
			frappe.get_all(
				"Item", filters={"item_group": ["in", list(groups)], "has_serial_no": 1}, pluck="name"
			)
		)

	return items


def has_equipment_access(item_code: str, user: str | None = None) -> bool:
	return item_code in get_allowed_items(user)
