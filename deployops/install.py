import frappe

from deployops.roles import DESK_ACCESS


def create_roles():
	"""Create the DeployOps roles if they are missing.

	Runs before install and before every migrate, so any site with the app has the roles.
	Roles that already exist are left as the site administrator configured them.
	"""
	for role, desk_access in DESK_ACCESS.items():
		if frappe.db.exists("Role", role):
			continue

		frappe.get_doc(
			{"doctype": "Role", "role_name": role, "desk_access": desk_access, "is_custom": 0}
		).insert(ignore_permissions=True)
