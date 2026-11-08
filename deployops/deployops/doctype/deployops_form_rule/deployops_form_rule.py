"""A Form Rule plans a form for every machine of an equipment category on jobs of one type (v2)."""

import frappe
from frappe import _
from frappe.model.document import Document

from deployops.forms import machine_forms

JOB = "DeployOps Job"


class DeployOpsFormRule(Document):
	def validate(self):
		form = frappe.db.get_value(
			"Form", self.form, ["context_doctype", "status", "current_version"], as_dict=True
		)
		if not form or form.context_doctype != JOB:
			frappe.throw(_("Form {0} is not a job form.").format(self.form))
		if form.status == "Archived":
			frappe.throw(_("Form {0} is archived.").format(self.form))
		if self.active and not form.current_version:
			frappe.throw(
				_("Form {0} has no published version, so an active rule cannot use it.").format(self.form)
			)
		duplicate = frappe.db.exists(
			self.doctype,
			{
				"job_type": self.job_type,
				"equipment_category": self.equipment_category,
				"form": self.form,
				"name": ["!=", self.name],
			},
		)
		if duplicate:
			frappe.throw(_("This rule already exists."))

	def on_update(self):
		_resync(self.job_type)
		before = self.get_doc_before_save()
		if before and before.job_type != self.job_type:
			_resync(before.job_type)

	def after_delete(self):
		# After the delete, so the resync no longer sees this rule.
		_resync(self.job_type)


def _resync(job_type: str) -> None:
	machine_forms.resync_job_type(job_type)
