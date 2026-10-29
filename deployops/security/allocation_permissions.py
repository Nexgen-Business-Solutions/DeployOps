"""Allocation visibility (#14), following the job rules (#12).

- Technician: the current allocation of machines on jobs assigned to them, for that job's customer,
  within their equipment profile. Not the machine's allocations for other customers (before or
  after their job), not cancelled machines, and nothing once their equipment is revoked.
- Supervisor / Manager: allocations of equipment in their profile.
- DeployOps Administrator / Administrator: all.
"""

import frappe

from deployops.security.equipment_access import get_allowed_items
from deployops.security.job_permissions import _sql_list, get_scope

ALLOCATION = "DeployOps Equipment Allocation"


def _technician_machines(user: str) -> set[tuple[str, str]]:
	"""(serial, customer) of machines on the user's jobs: not cancelled, equipment in their profile.

	The customer ties an allocation to the job: the same machine with another customer, before or
	after this job, is not theirs to see.
	"""
	allowed = get_allowed_items(user)
	if not allowed:
		return set()
	job = frappe.qb.DocType("DeployOps Job")
	device = frappe.qb.DocType("DeployOps Job Device")
	return {
		(row[0], row[1])
		for row in frappe.qb.from_(device)
		.join(job)
		.on(device.parent == job.name)
		.select(device.serial_no, job.customer)
		.where(device.parenttype == "DeployOps Job")
		.where(job.assigned_technician == user)
		.where(device.serial_no.isnotnull())
		.where(device.device_status != "Cancelled")
		.where(device.item_code.isin(list(allowed)))
		.run()
	}


def allocation_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	scope = get_scope(user)
	if scope == "all":
		return ""
	if scope == "assigned":
		# active_serial is set only on a serial's current allocation (Reserved / Deployed / Delivered).
		pairs = ", ".join(
			f"({_sql_list([serial])}, {_sql_list([customer])})"
			for serial, customer in _technician_machines(user)
		)
		if not pairs:
			return "1 = 0"
		return f"(`tab{ALLOCATION}`.`active_serial`, `tab{ALLOCATION}`.`customer`) in ({pairs})"
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
		active_serial = customer = None  # nothing is current before it is saved
		item_code = doc.item_code or frappe.db.get_value("Serial No", doc.serial_no, "item_code")
	else:
		active_serial, customer, item_code = frappe.db.get_value(
			ALLOCATION, doc.name, ["active_serial", "customer", "item_code"]
		)
	if scope == "all":
		return True
	if scope == "assigned":
		return bool(active_serial) and (active_serial, customer) in _technician_machines(user)
	if scope == "equipment":
		return item_code in get_allowed_items(user)
	return False
