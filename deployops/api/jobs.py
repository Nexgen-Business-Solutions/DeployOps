"""DeployOps Job API (#18 / #39): create a job from a source, and Desk pickers for source and serial."""

import frappe
from frappe import _

from deployops.api.sources import require_deployops_role, search_sources, visible_lines
from deployops.deployops.doctype.deployops_job.deployops_job import devices_from_source, serial_choices
from deployops.integrations import erpnext_sources
from deployops.roles import TECHNICIAN
from deployops.security.company_access import allowed_companies
from deployops.security.equipment_access import get_allowed_items, is_unrestricted
from deployops.workflow import job_workflow


@frappe.whitelist(methods=["POST"])
def make_job(
	source_doctype: str,
	source_name: str,
	job_type: str,
	company: str | None = None,
	planned_date: str | None = None,
	assigned_technician: str | None = None,
	equipment_category: str | None = None,
) -> str:
	"""Create a Draft job from an ERPNext source; devices are filled in from the source."""
	require_deployops_role()
	job = frappe.get_doc(
		{
			"doctype": "DeployOps Job",
			"job_type": job_type,
			"source_doctype": source_doctype,
			"source_name": source_name,
			"company": company or frappe.db.get_value(source_doctype, source_name, "company"),
			"planned_date": planned_date,
			"assigned_technician": assigned_technician,
			"equipment_category": equipment_category,
		}
	)
	job.insert()
	return job.name


@frappe.whitelist()
def get_source_details(source_doctype: str, source_name: str, company: str | None = None) -> dict:
	"""What a new job from this source will hold: customer, contact, site and device rows.

	Called by the form when the source is picked; uses the same logic and checks as saving.
	"""
	require_deployops_role()
	source = erpnext_sources.validate_source(source_doctype, source_name, company)
	snapshot = erpnext_sources.get_source_snapshot(source)
	if visible_lines(snapshot, frappe.session.user) is None:
		frappe.throw(
			_("You are not authorised for any equipment on {0} {1}.").format(_(source_doctype), source_name),
			frappe.PermissionError,
		)

	contact = snapshot["contact"] or {}
	address = snapshot["address"] or {}
	details = (contact.get(f) for f in ("full_name", "email_id", "phone", "mobile_no"))
	return {
		"company": snapshot["company"],
		"customer": snapshot["customer"],
		"customer_name": snapshot["customer_name"],
		"contact": contact.get("name"),
		"contact_display": "\n".join(value for value in details if value),
		"address": address.get("name"),
		"address_display": address.get("display"),
		"devices": devices_from_source(source, snapshot),
	}


@frappe.whitelist()
def source_link_query(
	doctype: str, txt: str, searchfield: str, start: int, page_len: int, filters: dict | str | None = None
):
	"""Desk picker for Job.source_name: usable sources holding the user's equipment."""
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	rows = search_sources(doctype, txt or "", company=filters.get("company"), limit=int(page_len or 20))
	return [[row["name"], row["customer_name"] or row["customer"], row["status"] or ""] for row in rows]


@frappe.whitelist()
def serial_link_query(
	doctype: str, txt: str, searchfield: str, start: int, page_len: int, filters: dict | str | None = None
):
	"""Desk picker for Job Device.serial_no.

	What the source allows (``serial_choices``): a delivery's serials, a subscription's allocated
	machines, an order's delivered serials plus stock for its undelivered units. Other sources:
	serials of the Item in the job's company — in stock only, except for Maintenance jobs.
	"""
	require_deployops_role()
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	item_code = filters.get("item_code")
	if not item_code:
		return []
	if not is_unrestricted(frappe.session.user) and item_code not in get_allowed_items():
		return []

	# The source decides which serials fit (deployops_job.serial_choices); stock is only offered
	# where the source leaves units open (an order's undelivered units) or does not decide.
	choices, stock_units = None, 0
	if filters.get("source_doctype") and filters.get("source_name"):
		erpnext_sources.validate_source(filters["source_doctype"], filters["source_name"])
		choices, stock_units = serial_choices(
			filters["source_doctype"], filters["source_name"], item_code, filters.get("delivery_note")
		)

	conditions = {"item_code": item_code, "name": ["like", f"%{txt or ''}%"]}
	# Only serials of the caller's companies (Company user permissions), whatever the client sends.
	companies = allowed_companies("Serial No")
	if filters.get("company"):
		companies = {filters["company"]} & companies if companies is not None else {filters["company"]}
	if companies is not None:
		conditions["company"] = ["in", list(companies) or [""]]
	if choices is not None:
		names = [s for s in choices if (txt or "").lower() in s.lower()]
		if stock_units:
			names += frappe.get_all(
				"Serial No",
				filters={**conditions, "status": "Active", "warehouse": ["is", "set"]},
				pluck="name",
			)
		conditions["name"] = ["in", names or [""]]
	else:
		if filters.get("job_type") != "Maintenance":
			conditions["status"] = "Active"

	return frappe.get_all(
		"Serial No",
		filters=conditions,
		fields=["name", "status"],
		limit_start=int(start or 0),
		limit_page_length=int(page_len or 20),
		order_by="name",
		as_list=True,
	)


@frappe.whitelist()
def technician_link_query(
	doctype: str, txt: str, searchfield: str, start: int, page_len: int, filters: dict | str | None = None
):
	"""Desk picker for Job.assigned_technician.

	Frappe's default User picker only lists Desk (System) users, and Technicians are Website Users,
	so this lists active DeployOps Technicians authorised for every machine on the job.
	"""
	require_deployops_role()
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	item_codes = set(filters.get("item_codes") or [])
	if not item_codes:
		return []

	technicians = frappe.get_all(
		"Has Role", filters={"role": TECHNICIAN, "parenttype": "User"}, pluck="parent", distinct=True
	)
	users = frappe.get_all(
		"User",
		filters={"name": ["in", technicians or [""]], "enabled": 1},
		or_filters={"name": ["like", f"%{txt or ''}%"], "full_name": ["like", f"%{txt or ''}%"]},
		fields=["name", "full_name"],
		order_by="full_name",
	)
	matches = [[user.name, user.full_name] for user in users if item_codes <= get_allowed_items(user.name)]
	return matches[int(start or 0) : int(start or 0) + int(page_len or 20)]


@frappe.whitelist()
def get_actions(job: str) -> dict:
	"""Workflow actions the current user may take on this job and on each of its machines."""
	require_deployops_role()
	doc = frappe.get_doc("DeployOps Job", job)
	doc.check_permission("read")
	return {"job": job_workflow.get_job_actions(doc), "devices": job_workflow.get_device_actions(doc)}


@frappe.whitelist(methods=["POST"])
def job_action(job: str, action: str, reason: str | None = None) -> str:
	require_deployops_role()
	return job_workflow.apply_job_action(job, action, reason)


@frappe.whitelist(methods=["POST"])
def device_action(job: str, device: str, action: str, reason: str | None = None) -> str:
	require_deployops_role()
	return job_workflow.apply_device_action(job, device, action, reason)
