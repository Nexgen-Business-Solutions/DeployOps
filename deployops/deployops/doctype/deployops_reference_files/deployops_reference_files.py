"""DeployOps Reference Files (#42): manuals and guides shown to technicians inside the checklists.

Administrators upload the files here; each row says which checklist (and optionally which section)
shows it. The files stay private: anyone who can read these settings (the DeployOps roles) can open
them, nobody else.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from deployops.checklists.cards import FORM_DOCTYPES

ALLOWED_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg")


class DeployOpsReferenceFiles(Document):
	def validate(self):
		for row in self.references:
			if not frappe.db.exists(
				"File",
				{
					"file_url": row.file,
					"is_private": 1,
					"attached_to_doctype": self.doctype,
					"attached_to_name": self.name,
				},
			):
				frappe.throw(
					_("Row #{0}: upload the file here as a private attachment of these settings.").format(
						row.idx
					)
				)
			if not (row.file or "").lower().endswith(ALLOWED_EXTENSIONS):
				frappe.throw(_("Row #{0}: only PDF or image files can be references.").format(row.idx))
			if row.checklist not in FORM_DOCTYPES:
				frappe.throw(_("Row #{0}: choose one of the checklists.").format(row.idx))
			if row.section:
				df = frappe.get_meta(row.checklist).get_field(row.section)
				if not df or df.fieldtype != "Section Break":
					frappe.throw(
						_("Row #{0}: {1} has no section {2}.").format(row.idx, _(row.checklist), row.section)
					)


def references_for(doctype: str) -> list[dict]:
	"""The reference files a checklist shows, in the order the administrator listed them."""
	return [
		{"title": row.title, "url": row.file, "section": row.section or None}
		for row in frappe.get_single("DeployOps Reference Files").references
		if row.checklist == doctype
	]
