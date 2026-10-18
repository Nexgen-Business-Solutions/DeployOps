"""Job visibility for Technicians (#18): they only see jobs assigned to them.

Supervisor, Manager and Admin scoping by equipment and management scope is #12.
"""

import frappe

from deployops.roles import ADMINISTRATOR, MANAGER, SUPERVISOR, TECHNICIAN

BROADER_ROLES = {SUPERVISOR, MANAGER, ADMINISTRATOR, "System Manager"}


def is_technician_only(user: str) -> bool:
	if user == "Administrator":
		return False
	roles = set(frappe.get_roles(user))
	return TECHNICIAN in roles and not roles & BROADER_ROLES


def job_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	if is_technician_only(user):
		return f"`tabDeployOps Job`.`assigned_technician` = {frappe.db.escape(user)}"
	return ""


def job_has_permission(doc, user: str | None = None, permission_type: str | None = None) -> bool:
	user = user or frappe.session.user
	if not is_technician_only(user):
		return True

	if isinstance(doc, str):
		doc = frappe.get_doc("DeployOps Job", doc)
	# Judge by the saved assignee, so editing the field in memory can neither grant nor lose access.
	if doc.is_new():
		return doc.assigned_technician == user
	return frappe.db.get_value("DeployOps Job", doc.name, "assigned_technician") == user
