"""The forms_core context provider for DeployOps jobs (v2 Plan 3, spec §7.1)."""

from typing import Any

import frappe
from forms_core.context import ContextProvider
from frappe import _

from deployops.forms import machine_forms
from deployops.roles import TECHNICIAN
from deployops.security.job_permissions import job_in_scope, job_query_conditions
from deployops.security.matrix import FORM_LETTERS
from deployops.workflow.job_workflow import CHECKLIST_STATES, CLOSED

JOB = "DeployOps Job"
DEVICE = "DeployOps Job Device"
FORM_ROW = "DeployOps Job Device Form"
SUBMISSION = "Form Submission"

# Frappe permission type -> Form Submission letter (FORM_LETTERS). Any other type is denied.
PTYPE_LETTERS = {
	"read": "r",
	"select": "r",
	"report": "r",
	"email": "r",
	"print": "p",
	"export": "e",
	"create": "c",
	"write": "w",  # an amend arrives as write
	"submit": "s",
	"cancel": "x",
}
ASSIGNEE_LETTERS = set("cws")  # count only from the Technician role, for the job's assignee
FILLING = {"create", "write", "submit"}

# Values a job form can fill from, as (value, label, forms_core field type).
VALUES = (
	("job", "Job", "text"),
	("job_type", "Job type", "text"),
	("customer", "Customer", "text"),
	("customer_name", "Customer name", "text"),
	("address", "Address", "long_text"),
	("contact", "Contact", "long_text"),
	("company", "Company", "text"),
	("planned_date", "Planned date", "date"),
	("technician", "Technician", "text"),
	("technician_user", "Technician user", "text"),
	("item_code", "Item code", "text"),
	("item_name", "Item name", "text"),
	("serial_no", "Serial no", "text"),
)


class JobFormProvider(ContextProvider):
	def values(self, context_name: str, context_row: str | None) -> dict[str, Any]:
		job = (
			frappe.db.get_value(
				JOB,
				context_name,
				[
					"name",
					"job_type",
					"customer",
					"customer_name",
					"address_display",
					"contact_display",
					"company",
					"planned_date",
					"assigned_technician",
				],
				as_dict=True,
			)
			or frappe._dict()
		)
		device = None
		if context_row:
			device = frappe.db.get_value(
				DEVICE,
				{"name": context_row, "parent": context_name, "parenttype": JOB},
				["item_code", "item_name", "serial_no"],
				as_dict=True,
			)
		device = device or frappe._dict()
		technician = job.assigned_technician
		return {
			"job": job.name,
			"job_type": job.job_type,
			"customer": job.customer,
			"customer_name": job.customer_name,
			"address": job.address_display,
			"contact": job.contact_display,
			"company": job.company,
			"planned_date": str(job.planned_date) if job.planned_date else None,
			"technician": frappe.db.get_value("User", technician, "full_name") if technician else None,
			"technician_user": technician,
			"item_code": device.item_code,
			"item_name": device.item_name,
			"serial_no": device.serial_no,
		}

	def value_catalog(self) -> list[dict]:
		return [{"value": value, "label": _(label), "type": kind} for value, label, kind in VALUES]

	def outcomes(self) -> list[dict]:
		return [
			{"effect": "block_machine", "label": _("Block the machine")},
			{"effect": "flag_for_review", "label": _("Flag for review")},
		]

	def can_start(self, context_name: str, context_row: str | None, form: str) -> str | None:
		# forms_core asks before its create check: tell a user outside the job nothing about it, and
		# take no lock for them.
		if not frappe.db.exists(JOB, context_name) or not job_in_scope(
			frappe.get_doc(JOB, context_name), frappe.session.user
		):
			return _("This job does not exist.")
		# Lock the job so two starts for the same machine and form cannot both pass the checks.
		status = frappe.db.get_value(JOB, context_name, "status", for_update=True)
		if status is None:
			return _("This job does not exist.")
		if status not in CHECKLIST_STATES:
			return _("A form can only be started while the job is being worked on.")
		device_status = _device_status(context_name, context_row)
		if device_status is None:
			return _("That machine is not on job {0}.").format(context_name)
		if device_status == "Cancelled":
			return _("This machine was cancelled on the job.")
		planned = {
			"parent": context_name,
			"parenttype": JOB,
			"device": context_row,
			"form": form,
			"removed": 0,
		}
		if not frappe.db.exists(FORM_ROW, planned):
			return _("This form is not planned for this machine.")
		started = {
			"context_doctype": JOB,
			"context_name": context_name,
			"context_row": context_row,
			"form": form,
			"docstatus": ["in", [0, 1]],
		}
		if frappe.db.exists(SUBMISSION, started):
			return _("This machine already has this form on this job.")
		return None

	def has_permission(self, submission, user: str, ptype: str) -> bool:
		letter = PTYPE_LETTERS.get(ptype)
		job_name = submission.get("context_name")
		if not letter or not job_name or not frappe.db.exists(JOB, job_name):
			return False
		job = frappe.get_doc(JOB, job_name)  # the saved job, so its assignee and status are the stored ones
		if not job_in_scope(job, user) or letter not in _letters(job.assigned_technician, user):
			return False
		if ptype == "write" and submission.get("docstatus") == 1:
			# A submitted form, its photos and signatures are final: Frappe judges an attached file's
			# write, create and delete by write on this submission. A cancelled one (docstatus 2)
			# stays writable because forms_core checks an amend as write on the cancelled original.
			return False
		if ptype in FILLING:
			device_status = _device_status(job_name, submission.get("context_row"))
			if ptype == "submit" and not _planned(job_name, submission):
				return False  # the form was removed from this machine after it was started
			return job.status in CHECKLIST_STATES and device_status not in (None, "Cancelled")
		if ptype == "cancel":
			return job.status not in CLOSED and bool(frappe.flags.deployops_form_cancel)
		return True

	def on_submit(self, submission) -> None:
		machine_forms.apply_outcomes(submission)

	def on_cancel(self, submission) -> None:
		machine_forms.on_form_cancel(submission)

	def query_conditions(self, user: str) -> str:
		condition = job_query_conditions(user)
		if not condition:
			return "1=1"  # unrestricted; forms_core reads an empty condition as deny
		return (
			"`tabForm Submission`.`context_name` in "
			f"(select `tabDeployOps Job`.`name` from `tabDeployOps Job` where {condition})"
		)


def _device_status(job: str, device: str | None) -> str | None:
	"""The machine's status on the job, or None when the row is not on it."""
	if not device:
		return None
	return frappe.db.get_value(DEVICE, {"name": device, "parent": job, "parenttype": JOB}, "device_status")


def _planned(job: str, submission) -> bool:
	"""True while the submission's form is still planned (not removed) for its machine."""
	return bool(
		frappe.db.exists(
			FORM_ROW,
			{
				"parent": job,
				"parenttype": JOB,
				"device": submission.get("context_row"),
				"form": submission.get("form"),
				"removed": 0,
			},
		)
	)


def _letters(assignee: str | None, user: str) -> set[str]:
	"""The user's Form Submission letters on a job with this saved assignee."""
	letters: set[str] = set()
	for role in frappe.get_roles(user):
		granted = set(FORM_LETTERS.get(role, ""))
		if role != TECHNICIAN or assignee != user:
			granted -= ASSIGNEE_LETTERS
		letters |= granted
	return letters
