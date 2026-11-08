"""Each machine's planned forms on a job (v2 Plan 3). Tasks 2 to 4 fill this module in.

A job's `device_forms` rows say which forms each machine needs. Form Rules set them until the
machine's first form is started; after that they only change through overrides.
"""

import frappe

from deployops.checklists.cards import form_for_device
from deployops.forms.rules import plan_rows, planned_forms
from deployops.workflow.job_workflow import CLOSED

JOB = "DeployOps Job"
SUBMISSION = "Form Submission"
FORM_ROW = "DeployOps Job Device Form"
ROW_FIELDS = (
	"device",
	"form",
	"form_title",
	"required",
	"sort_order",
	"origin",
	"removed",
	"submission",
	"flagged",
)
NUMERIC_FIELDS = {"required", "sort_order", "removed", "flagged"}
FROZEN_JOB_STATUSES = CLOSED | {"Pending Review"}


def frozen(job: str, device: str) -> bool:
	"""True once any form (draft, submitted or cancelled) was started for this machine."""
	return bool(
		frappe.db.exists(SUBMISSION, {"context_doctype": JOB, "context_name": job, "context_row": device})
	)


def row_values(row) -> dict:
	"""A form row as a plain dict of its DocType fields (and its name, when it has one)."""
	values = {field: row.get(field) for field in ROW_FIELDS}
	for field in NUMERIC_FIELDS:
		values[field] = int(values[field] or 0)
	for field in set(ROW_FIELDS) - NUMERIC_FIELDS:
		values[field] = values[field] or None
	if row.get("name"):
		values["name"] = row.get("name")
	return values


def _leave_alone(job_doc, device) -> bool:
	return (
		job_doc.status in FROZEN_JOB_STATUSES
		or device.device_status in CLOSED
		or form_for_device(job_doc.name, device.name) is not None
		or frozen(job_doc.name, device.name)
	)


def sync_job(job_doc) -> None:
	"""Bring the job's form rows in line with the Form Rules, in memory (the caller saves)."""
	for device in job_doc.devices:
		if not device.name:
			device.name = frappe.generate_hash(length=10)

	existing = [row_values(row) for row in job_doc.device_forms]
	titles: dict[str, str] = {}
	rows: list[dict] = []
	for device in job_doc.devices:
		if _leave_alone(job_doc, device):
			rows += [row for row in existing if row["device"] == device.name]
			continue
		planned = planned_forms(job_doc.job_type, device.item_code)
		for row in plan_rows(existing, planned, device.name):
			if not row.get("form_title"):
				if row["form"] not in titles:
					titles[row["form"]] = frappe.db.get_value("Form", row["form"], "title")
				row["form_title"] = titles[row["form"]]
			rows.append(row)
	job_doc.set("device_forms", rows)


def _snapshot(job_doc) -> list[tuple]:
	return [tuple(row_values(row)[field] for field in ROW_FIELDS) for row in job_doc.device_forms]


def resync_job_type(job_type: str) -> int:
	"""Resync every open job of this type after a rule change. Returns how many jobs were saved."""
	names = frappe.get_all(
		JOB,
		filters={"job_type": job_type, "status": ["not in", list(FROZEN_JOB_STATUSES)]},
		pluck="name",
	)
	saved = 0
	for name in names:
		job = frappe.get_doc(JOB, name)
		before = _snapshot(job)
		sync_job(job)
		if _snapshot(job) == before:
			continue
		job.flags.device_forms_sync = True
		job.save(ignore_permissions=True)
		saved += 1
	return saved


def active_rows(job_doc, device: str) -> list:
	"""The machine's form rows that are not removed, in order."""
	return [row for row in job_doc.device_forms if row.device == device and not row.removed]


def uses_forms(job_doc, device: str) -> bool:
	"""A machine uses forms (and is judged only by them) once it has a form row that is not removed."""
	return bool(active_rows(job_doc, device))


def on_submission_insert(doc, method=None) -> None:
	"""Form Submission `after_insert` hook: link a new job submission (a start or an amend) to the
	machine's active form row."""
	if doc.context_doctype != JOB:
		return
	row = frappe.db.get_value(
		FORM_ROW,
		{
			"parent": doc.context_name,
			"parenttype": JOB,
			"device": doc.context_row,
			"form": doc.form,
			"removed": 0,
		},
		"name",
	)
	if row:
		frappe.db.set_value(FORM_ROW, row, "submission", doc.name)
