"""Checklist report download (#27): the PDF of a submitted checklist, for whoever may print it."""

import frappe
from frappe.core.doctype.access_log.access_log import make_access_log

from deployops.api.checklists import form_doctype
from deployops.api.sources import require_deployops_role
from deployops.checklists import report


@frappe.whitelist(methods=["GET"])
def checklist_pdf(doctype: str, name: str, audience: str = "internal"):
	"""Same permission as printing the form (it follows job visibility); every download is logged."""
	require_deployops_role()
	doc = frappe.get_doc(form_doctype(doctype), name)
	doc.check_permission("print")
	report.check_reportable(doc, audience)
	content = report.render_pdf(doc, audience)
	make_access_log(doctype=doc.doctype, document=doc.name, file_type="PDF", method=f"Report: {audience}")
	suffix = "-customer" if audience == "customer" else ""
	frappe.local.response.filename = f"{doc.name}{suffix}.pdf"
	frappe.local.response.filecontent = content
	frappe.local.response.type = "pdf"
