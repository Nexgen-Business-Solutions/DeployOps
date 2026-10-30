import frappe

from deployops.roles import ALIASES, DESK_ACCESS


def role_user_email(role: str) -> str:
	return f"{ALIASES[role].lower()}@deployops.test"


def make_role_user(role: str) -> str:
	"""Create (or reuse) a user that holds exactly one DeployOps role and return its name."""
	email = role_user_email(role)
	expected_type = "System User" if DESK_ACCESS.get(role, 0) else "Website User"
	if not frappe.db.exists("User", email):
		user = frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": ALIASES[role], "send_welcome_email": 0}
		)
		user.append("roles", {"role": role})
		user.insert(ignore_permissions=True)
	else:
		user = frappe.get_doc("User", email)
		current_roles = {r.role for r in user.roles}
		needs_save = role not in current_roles or user.user_type != expected_type
		if expected_type == "Website User" and current_roles - {role}:
			# Stale desk-access roles (e.g. Desk User left from a previous drift to System User)
			# cause Frappe's validate to override user_type back to System User even after we fix it.
			# Strip them out so the save actually lands as Website User.
			user.roles = [r for r in user.roles if r.role == role]
			if not user.roles:
				user.append("roles", {"role": role})
			needs_save = True
		elif role not in current_roles:
			user.append("roles", {"role": role})
		if needs_save:
			user.save(ignore_permissions=True)
	return email


def api_token(user: str) -> str:
	"""Give `user` an API key and return the `Authorization` header that signs HTTP tests in as them.

	Use this rather than a `sid` in the URL: Frappe ignores a query-string sid on requests with a JSON
	body, which quietly turns them into guest requests (#35). Commit before the requests run.
	"""
	doc = frappe.get_doc("User", user)
	doc.api_key, secret = frappe.generate_hash(length=15), frappe.generate_hash(length=15)
	doc.api_secret = secret
	doc.save(ignore_permissions=True)
	return f"token {doc.api_key}:{secret}"
