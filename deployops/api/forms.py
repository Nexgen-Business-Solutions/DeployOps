"""Machine forms API (v2 Plan 3): a machine's forms on a job, start one, override, discard, cancel;
form cards, a form's jobs and the Supervisor report."""

import frappe
from forms_core.reports import schema
from forms_core.submissions import start
from frappe import _
from frappe.utils import cint

from deployops.api.sources import require_deployops_role
from deployops.forms import machine_forms as device_forms
from deployops.forms.provider import JobFormProvider, _letters
from deployops.roles import ADMINISTRATOR, MANAGER, SUPERVISOR
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


# ---------------------------------------------------------------------------------------------
# Cards, a form's jobs and the Supervisor report.

RULE = "DeployOps Form Rule"
DEVICE = "DeployOps Job Device"
REPORT_ROLES = {SUPERVISOR, MANAGER, ADMINISTRATOR}
MAX_PAGE_LENGTH = 200
SKIPPED_FIELDTYPES = set(frappe.model.no_value_fields)  # tables and layout fields


def _carded_forms() -> list[dict]:
	"""Published, non-archived Forms with an active Form Rule, by their lowest rule order, then title."""
	rules = frappe.get_all(RULE, filters={"active": 1}, fields=["form", "job_type", "sort_order"])
	if not rules:
		return []
	forms = frappe.get_all(
		"Form",
		filters={
			"name": ["in", list({rule.form for rule in rules})],
			"status": ["!=", "Archived"],
			"current_version": ["is", "set"],
		},
		fields=["name", "title", "subtitle", "icon", "color"],
	)
	cards = []
	for form in forms:
		own = [rule for rule in rules if rule.form == form.name]
		cards.append(
			{
				"form": form.name,
				"title": form.title,
				"subtitle": form.subtitle or None,
				"icon": form.icon or None,
				"color": form.color or None,
				"job_types": sorted({rule.job_type for rule in own}),
				"order": min(rule.sort_order or 0 for rule in own),
			}
		)
	return sorted(cards, key=lambda card: (card.pop("order"), card["title"] or ""))


def _job_form_rows(forms: list[str]) -> list[dict]:
	"""The active rows of `forms` on the user's visible open jobs, on machines that are not Cancelled:
	`[{"job", "form", "device", "outstanding", "flagged"}]`."""
	jobs = frappe.get_list(JOB, filters={"status": ["not in", list(CLOSED)]}, pluck="name")
	if not jobs or not forms:
		return []
	return frappe.db.sql(
		f"""
		select jdf.parent as job, jdf.form, jdf.device,
			(jdf.required = 1 and ifnull(fs.docstatus, 0) != 1) as outstanding, jdf.flagged
		from `tab{FORM_ROW}` jdf
		join `tab{DEVICE}` jd on jd.name = jdf.device and jd.parent = jdf.parent and jd.parenttype = %(job)s
		left join `tab{SUBMISSION}` fs on fs.name = jdf.submission
		where jdf.parenttype = %(job)s and jdf.parent in %(jobs)s and jdf.form in %(forms)s
			and jdf.removed = 0 and jd.device_status != 'Cancelled'
		""",
		{"job": JOB, "jobs": tuple(jobs), "forms": tuple(forms)},
		as_dict=True,
	)


def _with_counts(card: dict, rows: list[dict]) -> dict:
	own = [row for row in rows if row.form == card["form"]]
	outstanding = {row.job for row in own if row.outstanding}
	flagged = {row.job for row in own if row.flagged}
	attention = len(outstanding | flagged)
	return {
		**card,
		"open_jobs": len({row.job for row in own}),
		"outstanding": len(outstanding),
		"flagged": len(flagged),
		"attention": attention,
		"waiting": attention > 0,
	}


@frappe.whitelist(methods=["GET"])
def form_cards() -> list[dict]:
	"""One card per form that Form Rules plan, with counts over the user's visible open jobs."""
	require_deployops_role()
	cards = _carded_forms()
	rows = _job_form_rows([card["form"] for card in cards])
	return [_with_counts(card, rows) for card in cards]


@frappe.whitelist(methods=["GET"])
def form_jobs(form: str) -> dict:
	"""The form's card and the user's visible open jobs that have it on a machine."""
	require_deployops_role()
	card = next((card for card in _carded_forms() if card["form"] == form), None)
	if card is None:
		frappe.throw(_("Form {0} is not planned by any Form Rule.").format(form), frappe.DoesNotExistError)
	rows = _job_form_rows([form])
	by_job: dict[str, list] = {}
	for row in rows:
		by_job.setdefault(row.job, []).append(row)
	jobs = frappe.get_all(
		JOB,
		filters={"name": ["in", list(by_job) or [""]]},
		fields=["name", "job_type", "customer_name", "address_display", "planned_date", "status"],
		order_by="planned_date asc, modified desc",
	)
	for job in jobs:
		own = by_job[job.name]
		job.update(
			{
				"machines": len({row.device for row in own}),
				"outstanding": sum(1 for row in own if row.outstanding),
				"flagged": sum(1 for row in own if row.flagged),
			}
		)
	return {"card": _with_counts(card, rows), "jobs": jobs}


def _report_columns(parts: list[str]) -> list[dict]:
	"""Each part's visible value fields, in part order; later parts' `submission` link is left out."""
	columns, seen = [], set()
	for part in parts:
		for field in frappe.get_meta(part).fields:
			if field.hidden or field.fieldtype in SKIPPED_FIELDTYPES or field.fieldname in seen:
				continue
			seen.add(field.fieldname)
			columns.append({"fieldname": field.fieldname, "label": field.label, "fieldtype": field.fieldtype})
	return columns


@frappe.whitelist(methods=["GET"])
def report_rows(form: str, job: str | None = None, start: int = 0, page_length: int = 50) -> dict:
	"""The form's report rows (submitted and cancelled) on the jobs the user can see. Supervisor and
	up. Repeating tables are not included."""
	require_deployops_role()
	if not REPORT_ROLES & set(frappe.get_roles()):
		frappe.throw(_("You are not allowed to see form reports."), frappe.PermissionError)
	if frappe.db.get_value("Form", form, "context_doctype") != JOB:
		frappe.throw(_("Form {0} is not a job form.").format(form), frappe.DoesNotExistError)
	start = max(cint(start), 0)
	page_length = min(max(cint(page_length), 1), MAX_PAGE_LENGTH)
	filters = {"form": form, "context_doctype": JOB, "docstatus": ["in", [1, 2]]}
	if job:
		filters["context_name"] = job
	names = frappe.get_list(
		SUBMISSION,
		filters=filters,
		pluck="name",
		order_by="submitted_on desc",
		limit_start=start,
		limit_page_length=page_length,
	)
	total = len(frappe.get_list(SUBMISSION, filters=filters, pluck="name", limit_page_length=0))
	parts = schema.report_doctypes(form)["parts"]
	columns = _report_columns(parts)
	merged: dict[str, dict] = {name: {"name": name} for name in names}
	if names:
		wanted = {column["fieldname"] for column in columns}
		for part in parts:
			fields = ["name", *(f.fieldname for f in frappe.get_meta(part).fields if f.fieldname in wanted)]
			for row in frappe.get_all(part, filters={"name": ["in", names]}, fields=fields):
				merged[row.name].update(row)
	return {
		"status": frappe.db.get_value("Form Report", form, "status") or "Not built",
		"columns": columns,
		"rows": [merged[name] for name in names],
		"total": total,
		"start": start,
		"page_length": page_length,
	}


@frappe.whitelist(methods=["GET"])
def form_rule_counts() -> dict[str, int]:
	"""Active rule counts for the designer's forms list."""
	from forms_core.permissions import require_designer

	require_designer()
	counts = {}
	for row in frappe.get_all(RULE, filters={"active": 1}, fields=["form"]):
		counts[row.form] = counts.get(row.form, 0) + 1
	return counts


@frappe.whitelist(methods=["GET"])
def submission_pdf(name: str, audience: str = "internal"):
	"""The PDF of a submitted form entry, for whoever may read the entry; every download is logged."""
	from frappe.core.doctype.access_log.access_log import make_access_log

	from deployops.forms import report

	require_deployops_role()
	doc = frappe.get_doc(SUBMISSION, name)
	doc.check_permission("read")
	content = report.render_pdf(doc, audience)
	make_access_log(doctype=SUBMISSION, document=doc.name, file_type="PDF", method=f"Report: {audience}")
	suffix = "-customer" if audience == "customer" else ""
	frappe.local.response.filename = f"{doc.name}{suffix}.pdf"
	frappe.local.response.filecontent = content
	frappe.local.response.type = "pdf"


# Form Rules from the builder (designers): which jobs and machines get a job form.

RULE_FIELDS = ["name", "job_type", "equipment_category", "required", "active", "sort_order"]


def _require_designer():
	from forms_core.permissions import require_designer

	require_designer()


@frappe.whitelist(methods=["GET"])
def form_rules(form: str) -> dict:
	"""The form's rules, the choices for a new one, and how many open jobs each rule reaches."""
	_require_designer()
	rules = frappe.get_all(RULE, filters={"form": form}, fields=RULE_FIELDS, order_by="job_type, equipment_category")
	for rule in rules:
		rule["open_jobs"] = frappe.db.sql(
			"""select count(distinct df.parent) from `tabDeployOps Job Device Form` df
			join `tabDeployOps Job` j on j.name = df.parent
			where df.form = %s and df.origin = 'Rule' and ifnull(df.removed, 0) = 0 and j.job_type = %s
			and j.status not in ('Completed', 'Cancelled')""",
			(form, rule.job_type),
		)[0][0] if rule.active else 0
	job_types = [o for o in (frappe.get_meta(JOB).get_field("job_type").options or "").split("\n") if o]
	return {
		"rules": rules,
		"job_types": job_types,
		"categories": frappe.get_all("DeployOps Equipment Category", pluck="name", order_by="name"),
	}


@frappe.whitelist(methods=["POST"])
def save_form_rule(form: str, job_type: str, equipment_category: str, required=1, active=1, name: str | None = None) -> str:
	"""Create or change a rule; the rule's own checks apply and open jobs are re-planned."""
	_require_designer()
	doc = frappe.get_doc(RULE, name) if name else frappe.new_doc(RULE)
	if name and doc.form != form:
		frappe.throw(_("This rule belongs to another form."), frappe.PermissionError)
	doc.update({"form": form, "job_type": job_type, "equipment_category": equipment_category,
		"required": cint(required), "active": cint(active)})
	doc.save(ignore_permissions=True)
	return doc.name


@frappe.whitelist(methods=["POST"])
def delete_form_rule(name: str) -> None:
	_require_designer()
	frappe.delete_doc(RULE, name, ignore_permissions=True)
