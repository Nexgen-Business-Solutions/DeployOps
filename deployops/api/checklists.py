"""Checklist API (#41): start a machine's checklist form; cancel a submitted one (Manager)."""

import frappe
from frappe import _

from deployops.api.sources import require_deployops_role
from deployops.checklists.cards import FORM_DOCTYPES, card_for


def form_doctype(doctype: str) -> str:
	if doctype not in FORM_DOCTYPES:
		frappe.throw(_("Unknown checklist."), frappe.DoesNotExistError)
	return doctype


@frappe.whitelist(methods=["POST"])
def start_checklist(job: str, device: str) -> dict:
	"""Create the checklist for one machine on a job; the form follows the job type and machine."""
	require_deployops_role()
	job_doc = frappe.get_doc("DeployOps Job", job)
	job_doc.check_permission("read")
	row = next((r for r in job_doc.devices if r.name == device), None)
	if not row:
		frappe.throw(_("That machine is not on job {0}.").format(job))
	card = card_for(job_doc.job_type, row.item_code)
	if not card:
		frappe.throw(
			_(
				"No checklist is set up for {0} on a {1} job. Ask an administrator to set the checklist product line on its equipment category."
			).format(row.item_code, _(job_doc.job_type))
		)
	doc = frappe.get_doc({"doctype": card["doctype"], "job": job, "job_device": device})
	doc.insert()
	return {"doctype": doc.doctype, "name": doc.name}


@frappe.whitelist(methods=["POST"])
def cancel_checklist(doctype: str, name: str, reason: str) -> int:
	"""Void a submitted checklist (Manager). Frappe's own cancel also needs write permission, which
	the matrix deliberately does not give Managers, so the cancel right is checked here instead."""
	require_deployops_role()
	if not (reason or "").strip():
		frappe.throw(_("A reason is required to cancel a checklist."))
	doc = frappe.get_doc(form_doctype(doctype), name)
	if not frappe.has_permission(doctype, "cancel", doc):
		frappe.throw(_("You are not allowed to cancel this checklist."), frappe.PermissionError)
	if doc.docstatus != 1:
		frappe.throw(_("Only a submitted checklist can be cancelled."))
	doc.flags.ignore_permissions = True
	doc.cancel()
	doc.add_comment("Comment", _("Checklist cancelled: {0}").format(reason.strip()))
	return doc.docstatus
