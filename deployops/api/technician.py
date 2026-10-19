"""API for the React technician app: one call per screen, every rule enforced on the server.

Visibility (#12), workflow (#19), allocation (#14) and checklist rules (#41) are reused as they are;
these functions only shape the data each screen needs.
"""

import frappe
from frappe import _
from frappe.model import no_value_fields

from deployops.api.checklists import form_doctype
from deployops.api.sources import require_deployops_role
from deployops.checklists import layout
from deployops.checklists.cards import CARDS, CARDS_BY_ID, card_for, form_for_device, items_by_product_line
from deployops.checklists.form import HEADER_FIELDS
from deployops.roles import ALIASES, ALL_ROLES
from deployops.workflow import job_workflow

JOB = "DeployOps Job"
OPEN = ["not in", ["Completed", "Cancelled"]]


@frappe.whitelist()
def me() -> dict:
	require_deployops_role()
	user = frappe.session.user
	roles = [ALIASES[role] for role in ALL_ROLES if role in frappe.get_roles(user)]
	return {
		"user": user,
		"full_name": frappe.db.get_value("User", user, "full_name") or user,
		"roles": roles,
		"has_desk": frappe.db.get_value("User", user, "user_type") == "System User",
	}


def _jobs_for(card: dict, items: set[str]) -> list[dict]:
	"""My visible open jobs of the card's type with at least one of the card's machines."""
	jobs = frappe.get_list(
		JOB,
		filters={"job_type": card["job_type"], "status": OPEN},
		fields=["name", "customer_name", "address_display", "planned_date", "status", "modified"],
		order_by="planned_date asc, modified desc",
		limit_page_length=200,
	)
	result = []
	for job in jobs:
		machines = frappe.get_all(
			"DeployOps Job Device",
			filters={"parent": job.name, "parenttype": JOB, "device_status": ["!=", "Cancelled"]},
			pluck="item_code",
		)
		count = sum(1 for item in machines if item in items)
		if count:
			job["machines"] = count
			result.append(job)
	return result


@frappe.whitelist()
def home() -> list[dict]:
	require_deployops_role()
	lines = items_by_product_line()
	cards = []
	for card in CARDS:
		jobs = _jobs_for(card, lines.get(card["product_line"], set()))
		cards.append(
			{
				**card,
				"open_jobs": len(jobs),
				"waiting": any(job.status in ("Draft", "Returned for Correction") for job in jobs),
			}
		)
	return cards


@frappe.whitelist()
def my_jobs(card: str) -> dict:
	require_deployops_role()
	if card not in CARDS_BY_ID:
		frappe.throw(_("Unknown card."), frappe.DoesNotExistError)
	definition = CARDS_BY_ID[card]
	items = items_by_product_line().get(definition["product_line"], set())
	return {"card": definition, "jobs": _jobs_for(definition, items)}


def _machine(doc, row, device_actions) -> dict:
	form = form_for_device(doc.name, row.name)
	return {
		"row": row.name,
		"item_code": row.item_code,
		"item_name": row.item_name,
		"serial_no": row.serial_no,
		"status": row.device_status,
		"actions": device_actions.get(row.name, []),
		"checklist": {"doctype": form[0], "name": form[1], "submitted": form[2] == 1} if form else None,
		"can_start_checklist": not form
		and doc.status in job_workflow.WORKING
		and row.device_status != "Cancelled"
		and bool(card_for(doc.job_type, row.item_code)),
	}


@frappe.whitelist()
def job_view(job: str) -> dict:
	require_deployops_role()
	doc = frappe.get_doc(JOB, job)
	doc.check_permission("read")
	device_actions = job_workflow.get_device_actions(doc)
	return {
		"name": doc.name,
		"job_type": doc.job_type,
		"status": doc.status,
		"customer_name": doc.customer_name,
		"address": doc.address_display,
		"contact": doc.contact_display,
		"planned_date": doc.planned_date,
		"source": f"{doc.source_doctype} {doc.source_name}",
		"actions": job_workflow.get_job_actions(doc),
		"machines": [_machine(doc, row, device_actions) for row in doc.devices],
	}


def _form_content(doc) -> dict:
	"""A submitted form shows its snapshot, so it keeps the questions it was answered against."""
	if doc.docstatus and doc.submission_snapshot:
		snapshot = frappe.parse_json(doc.submission_snapshot)
		return {
			"sections": snapshot["sections"],
			"values": snapshot["values"],
			"signatures": snapshot.get("signatures") or layout.signatures(doc),
		}
	return {
		"sections": layout.sections(doc),
		"values": layout.values(doc),
		"signatures": layout.signatures(doc),
	}


@frappe.whitelist()
def form_view(doctype: str, name: str) -> dict:
	require_deployops_role()
	doc = frappe.get_doc(form_doctype(doctype), name)
	doc.check_permission("read")
	card = next(card for card in CARDS if card["doctype"] == doctype)
	return {
		"doctype": doctype,
		"name": doc.name,
		"title": card["title"],
		"intro": doc.INTRO,
		"form_version": doc.form_version,
		"job": doc.job,
		"header": {field: layout.as_text(doc.get(field)) for field in HEADER_FIELDS},
		"technician_name": frappe.db.get_value("User", doc.technician, "full_name")
		if doc.technician
		else None,
		"docstatus": doc.docstatus,
		"submitted_by": frappe.db.get_value("User", doc.modified_by, "full_name")
		if doc.docstatus == 1
		else None,
		"submitted_on": layout.as_text(doc.modified) if doc.docstatus == 1 else None,
		"can_edit": doc.docstatus == 0 and frappe.has_permission(doctype, "write", doc),
		**_form_content(doc),
	}


def _apply_table(doc, df, rows: list):
	child = frappe.get_meta(df.options)
	editable = [c.fieldname for c in child.fields if not c.read_only and c.fieldtype not in no_value_fields]
	if df.fieldname in doc.FIXED_ROWS:
		existing = doc.get(df.fieldname)
		for row, values in zip(existing, rows or [], strict=False):
			row.update({c: values.get(c) for c in editable if c in values})
		return
	doc.set(df.fieldname, [{c: values.get(c) for c in editable if c in values} for values in rows or []])


@frappe.whitelist(methods=["POST"])
def save_form(doctype: str, name: str, values: dict | str) -> dict:
	"""Partial save: only the given fields change; the form is re-checked on the server."""
	require_deployops_role()
	values = frappe.parse_json(values) if isinstance(values, str) else values or {}
	doc = frappe.get_doc(form_doctype(doctype), name)
	for fieldname, value in values.items():
		df = doc.meta.get_field(fieldname)
		if not df or fieldname in layout.SKIPPED or df.read_only:
			continue
		if df.fieldtype == "Table":
			_apply_table(doc, df, value)
		elif df.fieldtype not in no_value_fields:
			doc.set(fieldname, None if value == "" else value)
	doc.save()
	return {"modified": layout.as_text(doc.modified), "values": layout.values(doc)}


@frappe.whitelist(methods=["POST"])
def submit_form(doctype: str, name: str) -> dict:
	require_deployops_role()
	doc = frappe.get_doc(form_doctype(doctype), name)
	doc.submit()
	return {"docstatus": doc.docstatus}
