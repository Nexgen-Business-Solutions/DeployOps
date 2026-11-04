"""Flag machines already blocked by a checklist's answers (#25).

Before #25 a NO GO's unblock reason was decided from the live submitted form; it now comes from the
machine's ``blocked_by_checklist`` flag. A Blocked machine whose most recent submitted or cancelled
checklist blocks it gets the flag, so clearing it still needs a reason. When in doubt (blocked by
hand after such a form) the flag is set: asking for a reason is the safe side.
"""

import frappe

from deployops.checklists.cards import FORM_DOCTYPES

DEVICE = "DeployOps Job Device"


def execute():
	rows = frappe.get_all(
		DEVICE,
		filters={"parenttype": "DeployOps Job", "device_status": "Blocked", "blocked_by_checklist": 0},
		fields=["name", "parent"],
	)
	for row in rows:
		if _latest_form_blocks(row.parent, row.name):
			frappe.db.set_value(DEVICE, row.name, "blocked_by_checklist", 1, update_modified=False)


def _latest_form_blocks(job: str, device: str) -> bool:
	forms = []
	for doctype in FORM_DOCTYPES:
		for form in frappe.get_all(
			doctype,
			filters={"job": job, "job_device": device, "docstatus": ["in", (1, 2)]},
			fields=["name", "creation"],
		):
			forms.append((form.creation, doctype, form.name))
	if not forms:
		return False
	_, doctype, name = max(forms)
	return bool(frappe.get_doc(doctype, name).block_reason())
