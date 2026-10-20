"""Job visibility (#18 / #12): who sees which DeployOps Job.

- Technician: jobs assigned to them *and* within their current equipment access profile.
- Supervisor / Manager: jobs within their equipment access profile.
- Within a profile: a job with machines is in scope when *all* its machines are; a job without
  machines when its equipment category is theirs. A job with neither is unclassified and is seen by
  administrators only (deny by default).
- DeployOps Administrator and the Administrator user: every job (one definition,
  ``equipment_access.is_unrestricted``; System Manager alone grants nothing here).

Everything is judged from the *saved* job, so editing a job in memory can neither grant nor lose
access. These hooks cover lists, reports, link search, the API, print and attachments, because
Frappe routes all of them through has_permission / permission_query_conditions.
"""

import frappe

from deployops.roles import MANAGER, SUPERVISOR, TECHNICIAN
from deployops.security.equipment_access import get_allowed_categories, get_allowed_items, is_unrestricted

JOB = "DeployOps Job"
DEVICE = "DeployOps Job Device"
SCOPED_ROLES = {SUPERVISOR, MANAGER}


def get_scope(user: str) -> str:
	"""'all', 'equipment' (Supervisor / Manager), 'assigned' (Technician only) or 'none'."""
	if is_unrestricted(user):
		return "all"
	roles = set(frappe.get_roles(user))
	if roles & SCOPED_ROLES:
		return "equipment"
	if TECHNICIAN in roles:
		return "assigned"
	return "none"


def is_technician_only(user: str) -> bool:
	return get_scope(user) == "assigned"


def _sql_list(values) -> str:
	return ", ".join(frappe.db.escape(value) for value in values) or "''"


def job_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	scope = get_scope(user)
	if scope == "all":
		return ""
	if scope == "none":
		return "1 = 0"

	equipment = _equipment_condition(user)
	if scope == "assigned":
		return f"(`tabDeployOps Job`.`assigned_technician` = {frappe.db.escape(user)} and {equipment})"
	return equipment


def _equipment_condition(user: str) -> str:
	"""SQL: the job's machines (or, without machines, its category) are within the user's profile."""
	items = _sql_list(get_allowed_items(user))
	categories = _sql_list(get_allowed_categories(user))
	has_devices = (
		f"exists (select 1 from `tab{DEVICE}` d where d.parent = `tabDeployOps Job`.`name` "
		f"and d.parenttype = '{JOB}')"
	)
	foreign_device = (
		f"exists (select 1 from `tab{DEVICE}` d where d.parent = `tabDeployOps Job`.`name` "
		f"and d.parenttype = '{JOB}' and d.item_code not in ({items}))"
	)
	return (
		f"(({has_devices} and not {foreign_device}) or (not {has_devices} and "
		f"`tabDeployOps Job`.`equipment_category` in ({categories})))"
	)


def job_in_scope(doc, user: str) -> bool:
	scope = get_scope(user)
	if scope == "all":
		return True
	if scope == "none":
		return False

	if doc.is_new():
		assignee, category = doc.assigned_technician, doc.equipment_category
		device_items = {row.item_code for row in doc.devices}
	else:
		assignee, category = frappe.db.get_value(JOB, doc.name, ["assigned_technician", "equipment_category"])
		device_items = set(
			frappe.get_all(DEVICE, filters={"parent": doc.name, "parenttype": JOB}, pluck="item_code")
		)

	if scope == "assigned" and assignee != user:
		return False
	if device_items:
		return device_items <= get_allowed_items(user)
	if doc.is_new():
		# Being created: its machines are filled from the source during validate, which also checks
		# the creator's equipment access. An unsaved job exposes nothing yet.
		return not category or category in get_allowed_categories(user)
	return bool(category) and category in get_allowed_categories(user)


def job_has_permission(doc, user: str | None = None, permission_type: str | None = None) -> bool:
	user = user or frappe.session.user
	if isinstance(doc, str):
		doc = frappe.get_doc(JOB, doc)
	return job_in_scope(doc, user)


# Checklist forms (#41) are visible exactly when their job is.
def form_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	if not doctype:
		return "1 = 0"  # fail closed: the condition must name the form's own table
	conditions = job_query_conditions(user)
	if not conditions:
		return conditions
	return f"`tab{doctype}`.`job` in (select `tabDeployOps Job`.`name` from `tabDeployOps Job` where {conditions})"


def form_has_permission(doc, user: str | None = None, permission_type: str | None = None) -> bool:
	user = user or frappe.session.user
	job = doc.job if doc.is_new() else frappe.db.get_value(doc.doctype, doc.name, "job")
	if not job or not frappe.db.exists(JOB, job):
		return False
	return job_in_scope(frappe.get_doc(JOB, job), user)
