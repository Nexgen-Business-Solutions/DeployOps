"""Equipment access profiles (#11 / #36): which equipment a user may work with.

Effective access = role (matrix.py) ∩ equipment profile (this module) ∩ job scope (#12).
Everything is read live from the database, so a revoked category stops working immediately.
DeployOps Administrators configure the categories and are not restricted by profiles.
"""

import frappe
from frappe.utils.nestedset import get_descendants_of

from deployops.roles import ADMINISTRATOR

CATEGORY = "DeployOps Equipment Category"
PROFILE = "DeployOps Equipment Access Profile"


def is_unrestricted(user: str) -> bool:
	return user == "Administrator" or ADMINISTRATOR in frappe.get_roles(user)


def get_allowed_categories(user: str | None = None) -> list[str]:
	"""Enabled categories the user may work with."""
	user = user or frappe.session.user
	enabled = frappe.get_all(CATEGORY, filters={"enabled": 1}, pluck="name")
	if is_unrestricted(user):
		return enabled

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

	categories = get_allowed_categories(user)
	if not categories:
		return set()

	items = set(
		frappe.get_all(
			f"{CATEGORY} Item",
			filters={"parent": ["in", categories], "parenttype": CATEGORY},
			pluck="item_code",
		)
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
