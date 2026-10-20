"""Allocation visibility (#14), following the job rules (#12).

- Technician: allocations of machines on jobs assigned to them.
- Supervisor / Manager: allocations of equipment in their profile.
- DeployOps Administrator / Administrator: all.
"""

import frappe

from deployops.security.equipment_access import get_allowed_items
from deployops.security.job_permissions import _sql_list, get_scope

ALLOCATION = "DeployOps Equipment Allocation"


def _technician_serials(user: str) -> set[str]:
	job = frappe.qb.DocType("DeployOps Job")
	device = frappe.qb.DocType("DeployOps Job Device")
	return {
		row[0]
		for row in frappe.qb.from_(device)
		.join(job)
		.on(device.parent == job.name)
		.select(device.serial_no)
		.where(device.parenttype == "DeployOps Job")
		.where(job.assigned_technician == user)
		.where(device.serial_no.isnotnull())
		.run()
	}


def allocation_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	scope = get_scope(user)
	if scope == "all":
		return ""
	if scope == "assigned":
		return f"`tab{ALLOCATION}`.`serial_no` in ({_sql_list(_technician_serials(user))})"
	if scope == "equipment":
		return f"`tab{ALLOCATION}`.`item_code` in ({_sql_list(get_allowed_items(user))})"
	return "1 = 0"


def allocation_has_permission(doc, user: str | None = None, permission_type: str | None = None) -> bool:
	user = user or frappe.session.user
	scope = get_scope(user)
	if isinstance(doc, str):
		doc = frappe.get_doc(ALLOCATION, doc)
	if doc.is_new():
		# item_code is only fetched from the serial during validate, after this check.
		serial_no = doc.serial_no
		item_code = doc.item_code or frappe.db.get_value("Serial No", serial_no, "item_code")
	else:
		serial_no, item_code = frappe.db.get_value(ALLOCATION, doc.name, ["serial_no", "item_code"])
	if scope == "all":
		return True
	if scope == "assigned":
		return serial_no in _technician_serials(user)
	if scope == "equipment":
		return item_code in get_allowed_items(user)
	return False
