import frappe

from deployops.roles import ALIASES


def role_user_email(role: str) -> str:
	return f"{ALIASES[role].lower()}@deployops.test"


def make_role_user(role: str) -> str:
	"""Create (or reuse) a user that holds exactly one DeployOps role and return its name."""
	email = role_user_email(role)
	if not frappe.db.exists("User", email):
		user = frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": ALIASES[role], "send_welcome_email": 0}
		)
		user.append("roles", {"role": role})
		user.insert(ignore_permissions=True)
	return email
