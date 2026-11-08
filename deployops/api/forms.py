"""Machine forms API (v2 Plan 3): a machine's forms on a job, start one, override, discard, cancel."""

import frappe
from forms_core.submissions import start
from frappe import _

from deployops.api.sources import require_deployops_role
from deployops.forms import machine_forms as device_forms
from deployops.forms.provider import JobFormProvider, _letters
from deployops.roles import MANAGER
from deployops.workflow.job_workflow import APPROVER_CAP, CLOSED, _device_label, _log, _save, capacities

JOB = "DeployOps Job"
SUBMISSION = "Form Submission"
FORM_ROW = "DeployOps Job Device Form"
AMEND_FIELDS = ("account", "form", "form_version", "context_doctype", "context_name", "context_row")


def _job_and_device(job: str, row: str):
	job_doc = frappe.get_doc(JOB, job)
	job_doc.check_permission("read")
	device = next((d for d in job_doc.devices if d.name == row), None)
	if device is None:
		frappe.throw(_("That machine is not on job {0}.").format(job))
	return job_doc, device


def _forms_list(value) -> list[str]:
	"""A list of form names from a JSON string, a list or None, without repeats."""
	if not value:
		return []
	if isinstance(value, str):
		try:
			value = frappe.parse_json(value)
		except ValueError:
			value = None
	if not isinstance(value, list) or not all(isinstance(form, str) and form for form in value):
		frappe.throw(_("Forms must be given as a list of form names."))
	return list(dict.fromkeys(value))


def _submission_info(name: str | None) -> dict:
	if not name:
		return frappe._dict()
	return (
		frappe.db.get_value(SUBMISSION, name, ["docstatus", "form_version"], as_dict=True) or frappe._dict()
	)


@frappe.whitelist(methods=["GET"])
def machine_forms(job: str, row: str) -> dict:
	"""The machine's active forms on the job, with what the session user may do with each."""
	require_deployops_role()
	job_doc, device = _job_and_device(job, row)
	user = frappe.session.user
	letters = _letters(job_doc.assigned_technician, user)
	provider = JobFormProvider()
	blocked = device_forms.override_problem(job_doc, device)
	is_manager = MANAGER in frappe.get_roles()
	active = device_forms.active_rows(job_doc, row)
	meta = {
		form.name: form
		for form in frappe.get_all(
			"Form",
			filters={"name": ["in", [r.form for r in active] or [""]]},
			fields=["name", "title", "subtitle", "icon", "color"],
		)
	}
	forms = []
	for form_row in active:
		info = _submission_info(form_row.submission)
		status = device_forms.row_status(form_row)
		cancelled = info.get("docstatus") == 2
		form = meta.get(form_row.form) or frappe._dict()
		can_start = (
			status == "Not started"
			and "c" in letters
			and (not cancelled or "w" in letters)  # restarting a cancelled form amends it
			and provider.can_start(job, row, form_row.form) is None
		)
		forms.append(
			{
				"form": form_row.form,
				"title": form.title or form_row.form_title,
				"subtitle": form.subtitle or None,
				"icon": form.icon or None,
				"color": form.color or None,
				"required": bool(form_row.required),
				"origin": form_row.origin,
				"status": status,
				"submission": form_row.submission or None,
				"form_version": info.get("form_version"),
				"flagged": bool(form_row.flagged),
				"can_start": bool(can_start),
				"can_remove": blocked is None
				and status == "Not started"
				and (is_manager or not form_row.required),
				"remove_needs_manager": bool(form_row.required),
			}
		)
	active_forms = {r.form for r in active}
	can_add = device_forms.add_problem(job_doc, device) is None
	return {
		"job": job_doc.name,
		"row": row,
		"item_code": device.item_code,
		"serial_no": device.serial_no or None,
		"device_status": device.device_status,
		"job_status": job_doc.status,
		"frozen": device_forms.frozen(job, row),
		"uses_forms": bool(active),
		"forms": forms,
		"can_add": can_add,
		"addable": [f for f in device_forms.addable_forms() if f["form"] not in active_forms]
		if can_add
		else [],
	}


@frappe.whitelist(methods=["POST"])
def start_machine_form(job: str, row: str, form: str) -> dict:
	"""The machine's live submission of this form, or a new one (an amendment after a cancel)."""
	require_deployops_role()
	job_doc, _device = _job_and_device(job, row)
	live = device_forms.live_submission(job, row, form)
	if live:
		return {"submission": live, "created": False}
	planned = next((r for r in device_forms.active_rows(job_doc, row) if r.form == form), None)
	if planned and planned.submission and _submission_info(planned.submission).get("docstatus") == 2:
		original = frappe.db.get_value(SUBMISSION, planned.submission, AMEND_FIELDS, as_dict=True)
		doc = frappe.get_doc({"doctype": SUBMISSION, "amended_from": planned.submission, **original})
		doc.insert()
		return {"submission": doc.name, "created": True}
	return {"submission": start(form, JOB, job, row), "created": True}


@frappe.whitelist(methods=["POST"])
def override_machine_forms(
	job: str,
	row: str,
	add: list[str] | str | None = None,
	remove: list[str] | str | None = None,
	required: int = 0,
	reason: str | None = None,
) -> dict:
	"""Add and remove the machine's forms (an approver; a required form needs a manager and a reason)."""
	require_deployops_role()
	job_doc, device = _job_and_device(job, row)
	problem = device_forms.override_problem(job_doc, device)
	if problem:
		denied = APPROVER_CAP not in capacities(job_doc, frappe.session.user)
		frappe.throw(problem, frappe.PermissionError if denied else frappe.ValidationError)
	device_forms.override(
		job_doc, device, _forms_list(add), _forms_list(remove), bool(frappe.utils.cint(required)), reason
	)
	return machine_forms(job, row)


def _job_submission(submission: str):
	doc = frappe.get_doc(SUBMISSION, submission)
	if doc.context_doctype != JOB:
		frappe.throw(_("This form is not on a job."))
	job_doc = frappe.get_doc(JOB, doc.context_name)
	job_doc.check_permission("read")
	return doc, job_doc


@frappe.whitelist(methods=["POST"])
def discard_machine_form(submission: str, reason: str) -> None:
	"""Delete a draft job form (a manager), logged with the reason; the machine can start it afresh."""
	require_deployops_role()
	doc, job_doc = _job_submission(submission)
	if "x" not in _letters(job_doc.assigned_technician, frappe.session.user):
		frappe.throw(_("You are not allowed to discard this form."), frappe.PermissionError)
	if doc.docstatus != 0:
		frappe.throw(_("Only a draft form can be discarded."))
	if job_doc.status in CLOSED:
		frappe.throw(_("Forms cannot be discarded on a {0} job.").format(_(job_doc.status)))
	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("A reason is required to discard a form."))
	device = next((d for d in job_doc.devices if d.name == doc.context_row), None)
	form_row = next((r for r in job_doc.device_forms if r.submission == doc.name), None)
	title = device_forms._title(doc, form_row)
	status = device.device_status if device else None
	_log(
		job_doc,
		frappe.session.user,
		"form: draft discarded",
		status,
		status,
		f"{title} ({doc.name}): {reason}",
		device=_device_label(device) if device else None,
	)
	_save(job_doc)
	# The row links the draft: point it back at the cancelled original (so the next start amends
	# it again), or clear it, before the delete, which is refused while the draft is linked.
	if form_row is not None:
		frappe.db.set_value(FORM_ROW, form_row.name, "submission", doc.amended_from or None)
	frappe.delete_doc(SUBMISSION, doc.name, ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def cancel_machine_form(submission: str, reason: str) -> int:
	"""Cancel a submitted job form (a manager) with a reason. Returns its docstatus (2)."""
	require_deployops_role()
	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("A reason is required to cancel a form."))
	doc, _job_doc = _job_submission(submission)
	frappe.flags.deployops_form_cancel = reason
	try:
		doc.check_permission("cancel")  # granted only while the reason flag is set
		# Frappe's cancel also checks write, which is final on a submitted form.
		doc.flags.ignore_permissions = True
		doc.cancel()
	finally:
		frappe.flags.pop("deployops_form_cancel", None)
	return doc.docstatus
