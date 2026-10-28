"""ERPNext source lookups for Desk and the React frontend

Any user with a DeployOps role may call these; guests and users without a DeployOps role may not.
Results are limited to the equipment in the caller's access profile (Admin is unrestricted) and
to the companies allowed by the caller's Company user permissions, if any.
"""

import frappe
from frappe import _

from deployops.integrations import erpnext_sources
from deployops.roles import ALL_ROLES
from deployops.security.company_access import allowed_companies
from deployops.security.equipment_access import get_allowed_items, is_unrestricted

MAX_SEARCH_RESULTS = 50


def require_deployops_role():
	if not set(ALL_ROLES) & set(frappe.get_roles()):
		frappe.throw(_("You need a DeployOps role to look up source documents."), frappe.PermissionError)


def visible_lines(snapshot: dict, user: str) -> list[dict] | None:
	"""Lines the user may see, or None when the source has equipment but none of it is theirs.

	A Subscription carries no equipment (devices are allocated separately, #14), so it is not
	refused for lack of equipment.
	"""
	if is_unrestricted(user) or snapshot["doctype"] == erpnext_sources.SUBSCRIPTION:
		return snapshot["lines"]

	allowed = get_allowed_items(user)
	lines = [line for line in snapshot["lines"] if line["item_code"] in allowed]
	return lines or None


@frappe.whitelist()
def get_source_summary(doctype: str, name: str, company: str | None = None) -> dict:
	require_deployops_role()
	doc = erpnext_sources.validate_source(doctype, name, company)
	snapshot = erpnext_sources.get_source_snapshot(doc)

	lines = visible_lines(snapshot, frappe.session.user)
	if lines is None:
		frappe.throw(
			_("You are not authorised for any equipment on {0} {1}.").format(_(doctype), name),
			frappe.PermissionError,
		)

	snapshot["lines"] = lines
	return snapshot


@frappe.whitelist()
def search_sources(doctype: str, txt: str = "", company: str | None = None, limit: int = 20) -> list[dict]:
	"""Usable sources of one type that match `txt` (name or customer) and hold the user's equipment."""
	require_deployops_role()
	if doctype not in erpnext_sources.SOURCE_DOCTYPES:
		frappe.throw(_("{0} is not a DeployOps source document.").format(doctype))

	limit = max(1, min(int(limit), MAX_SEARCH_RESULTS))
	customer_field = "party" if doctype == erpnext_sources.SUBSCRIPTION else "customer"
	filters = {"docstatus": ["!=", 2]}
	if company:
		filters["company"] = company
	companies = allowed_companies(doctype)
	if companies is not None:
		filters["company"] = ["in", list(companies & {company} if company else companies) or [""]]
	or_filters = {"name": ["like", f"%{txt}%"], customer_field: ["like", f"%{txt}%"]} if txt else None

	results = []
	for name in frappe.get_all(
		doctype,
		filters=filters,
		or_filters=or_filters,
		pluck="name",
		order_by="modified desc",
		limit=limit * 5,
	):
		doc = frappe.get_doc(doctype, name)
		if erpnext_sources.state_problem(doc):
			continue

		snapshot = erpnext_sources.get_source_snapshot(doc)
		if visible_lines(snapshot, frappe.session.user) is None:
			continue

		results.append(
			{
				"doctype": doctype,
				"name": name,
				"customer": snapshot["customer"],
				"customer_name": snapshot["customer_name"],
				"status": snapshot["status"],
				"company": snapshot["company"],
			}
		)
		if len(results) == limit:
			break

	return results


@frappe.whitelist()
def get_serial(serial_no: str, item_code: str | None = None, company: str | None = None) -> dict:
	require_deployops_role()
	serial = erpnext_sources.validate_serial(serial_no, item_code, company)

	user = frappe.session.user
	if not is_unrestricted(user) and serial.item_code not in get_allowed_items(user):
		frappe.throw(
			_("You are not authorised for equipment {0}.").format(serial.item_code), frappe.PermissionError
		)

	return serial
