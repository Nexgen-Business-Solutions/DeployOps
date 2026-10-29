"""Equipment allocation API (#14 / #38)."""

import frappe
from frappe import _

from deployops.api.sources import require_deployops_role
from deployops.equipment import allocations
from deployops.equipment.allocations import ALLOCATION, CANCEL_ROLES, HANDLER_ROLES
from deployops.integrations import erpnext_sources
from deployops.security.company_access import allowed_companies
from deployops.security.equipment_access import get_allowed_items, is_unrestricted


@frappe.whitelist(methods=["POST"])
def reserve(serial_no: str, source_doctype: str, source_name: str, company: str | None = None) -> str:
	require_deployops_role()
	return allocations.reserve(serial_no, source_doctype, source_name, company).name


@frappe.whitelist(methods=["POST"])
def return_machine(allocation: str, condition: str, returned_on: str | None = None) -> str:
	require_deployops_role()
	return allocations.return_allocation(allocation, condition, returned_on)


@frappe.whitelist(methods=["POST"])
def swap_machine(allocation: str, new_serial_no: str, condition: str) -> str:
	require_deployops_role()
	return allocations.swap(allocation, new_serial_no, condition)


@frappe.whitelist(methods=["POST"])
def cancel_reservation(allocation: str, reason: str) -> str:
	require_deployops_role()
	return allocations.cancel(allocation, reason)


@frappe.whitelist()
def get_allocation_actions(allocation: str) -> list[str]:
	"""Buttons for the allocation form: return, swap, cancel."""
	require_deployops_role()
	doc = frappe.get_doc(ALLOCATION, allocation)
	doc.check_permission("read")
	roles = set(frappe.get_roles())
	actions = []
	if doc.allocation_type == allocations.RENTAL and doc.status == "Deployed" and roles & HANDLER_ROLES:
		actions += ["return", "swap"]
	if doc.status == "Reserved" and roles & CANCEL_ROLES:
		actions.append("cancel")
	return actions


@frappe.whitelist()
def serial_history(serial_no: str) -> list[dict]:
	require_deployops_role()
	item_code = erpnext_sources.validate_serial(serial_no).item_code  # exists, caller's companies
	if not is_unrestricted(frappe.session.user) and item_code not in get_allowed_items():
		frappe.throw(_("You are not authorised for equipment {0}.").format(item_code), frappe.PermissionError)
	return allocations.get_serial_history(serial_no)


@frappe.whitelist()
def in_stock_serial_query(
	doctype: str, txt: str, searchfield: str, start: int, page_len: int, filters: dict | str | None = None
):
	"""Desk picker for Allocation.serial_no: in-stock machines of the user's equipment, not allocated."""
	require_deployops_role()
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	conditions = [
		["status", "=", "Active"],
		["warehouse", "is", "set"],
		["name", "like", f"%{txt or ''}%"],
		["item_code", "in", list(get_allowed_items()) or [""]],
	]
	if filters.get("company"):
		conditions.append(["company", "=", filters["company"]])
	companies = allowed_companies("Serial No")  # the caller's companies, whatever the client sends
	if companies is not None:
		conditions.append(["company", "in", list(companies)])
	taken = frappe.get_all(ALLOCATION, filters={"active_serial": ["is", "set"]}, pluck="active_serial")
	if taken:
		conditions.append(["name", "not in", taken])
	rows = frappe.get_all(
		"Serial No", filters=conditions, fields=["name", "item_code"], order_by="name", as_list=True
	)
	return rows[int(start or 0) : int(start or 0) + int(page_len or 20)]
