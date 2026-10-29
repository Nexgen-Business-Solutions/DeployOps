"""Job workflow (#19): states, who may move a job or a machine, the checks, and the status log.

Paths per job type:
  Pre-installation: Draft → In Preparation → Pending Review → Completed
  Installation:     Draft → Ready for Deployment → On Site → Pending Review → Completed
  Maintenance:      Draft → On Site → Pending Review → Completed
Side states: Blocked, Returned for Correction, Cancelled.

Approvers (Supervisor, Manager) and cancellers (Manager, Admin) come from the permission matrix
letters "a" and "x". Every move is checked on the server and written to the job's status log.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

from deployops.checklists.cards import card_for, form_for_device
from deployops.roles import ALL_ROLES, TECHNICIAN
from deployops.security.matrix import DOCTYPE_MATRIX

JOB = "DeployOps Job"
APPROVER_ROLES = {role for role in ALL_ROLES if "a" in DOCTYPE_MATRIX[JOB][role]}
CANCELLER_ROLES = {role for role in ALL_ROLES if "x" in DOCTYPE_MATRIX[JOB][role]}

PATHS = {
	"Pre-installation": ["Draft", "In Preparation", "Pending Review", "Completed"],
	"Installation": ["Draft", "Ready for Deployment", "On Site", "Pending Review", "Completed"],
	"Maintenance": ["Draft", "On Site", "Pending Review", "Completed"],
}
CLOSED = {"Completed", "Cancelled"}
WORKING = {"In Preparation", "On Site", "Returned for Correction"}  # machines can be worked on
ACTIVE = {"In Preparation", "Ready for Deployment", "On Site", "Pending Review", "Returned for Correction"}
REASON_REQUIRED = {"block", "return", "cancel"}

TECHNICIAN_CAP, APPROVER_CAP, CANCELLER_CAP = "technician", "approver", "canceller"


def capacities(job, user: str) -> set[str]:
	"""In which capacities the user acts on this job (judged on the saved assignee)."""
	roles = set(frappe.get_roles(user))
	caps = set()
	assignee = frappe.db.get_value(JOB, job.name, "assigned_technician")
	if TECHNICIAN in roles and assignee == user:
		caps.add(TECHNICIAN_CAP)
	if roles & APPROVER_ROLES:
		caps.add(APPROVER_CAP)
	if roles & CANCELLER_ROLES:
		caps.add(CANCELLER_CAP)
	return caps


# ---------------------------------------------------------------------------------------------
# Job-level actions


def _job_rules(job) -> dict:
	path = PATHS[job.job_type]
	return {
		"start": {"from": {"Draft"}, "to": path[1], "who": {APPROVER_CAP}, "label": _("Start")},
		"arrive": {
			"from": {"Ready for Deployment"},
			"to": "On Site",
			"who": {TECHNICIAN_CAP},
			"label": _("Arrived on Site"),
		},
		"submit": {
			"from": {path[-3], "Returned for Correction"},
			"to": "Pending Review",
			"who": {TECHNICIAN_CAP},
			"label": _("Submit for Review"),
		},
		"approve": {
			"from": {"Pending Review"},
			"to": "Completed",
			"who": {APPROVER_CAP},
			"label": _("Approve"),
		},
		"return": {
			"from": {"Pending Review"},
			"to": "Returned for Correction",
			"who": {APPROVER_CAP},
			"label": _("Return for Correction"),
		},
		"block": {
			"from": ACTIVE,
			"to": "Blocked",
			"who": {TECHNICIAN_CAP, APPROVER_CAP},
			"label": _("Block"),
		},
		"unblock": {"from": {"Blocked"}, "to": None, "who": {APPROVER_CAP}, "label": _("Unblock")},
		"cancel": {
			"from": (set(path) | {"Blocked", "Returned for Correction"}) - CLOSED,
			"to": "Cancelled",
			"who": {CANCELLER_CAP},
			"label": _("Cancel Job"),
		},
	}


def _job_check(job, action: str) -> str | None:
	"""Business check for a move; returns the problem or None."""
	if action == "start" and not job.assigned_technician:
		return _("assign a technician first")

	if action in ("submit", "approve"):
		active = [row for row in job.devices if row.device_status != "Cancelled"]
		if not active:
			return _("there is no machine to complete")
		for row in job.devices:
			if row.device_status == "Blocked":
				return _("machine {0} is blocked").format(_device_label(row))
			if row.device_status not in ("Completed", "Cancelled"):
				return _("machine {0} is not completed").format(_device_label(row))
			if row.device_status == "Completed" and not row.serial_no:
				return _("machine {0} has no Serial No").format(_device_label(row))
	return None


def get_job_actions(job, user: str | None = None) -> list[dict]:
	user = user or frappe.session.user
	caps = capacities(job, user)
	actions = []
	for action, rule in _job_rules(job).items():
		if job.status in rule["from"] and caps & rule["who"]:
			actions.append(
				{"action": action, "label": rule["label"], "reason_required": action in REASON_REQUIRED}
			)
	return actions


def apply_job_action(job_name: str, action: str, reason: str | None = None, user: str | None = None) -> str:
	user = user or frappe.session.user
	job = frappe.get_doc(JOB, job_name)
	job.check_permission("read")

	rule = _job_rules(job).get(action)
	if not rule:
		frappe.throw(_("Unknown job action {0}.").format(action))
	if job.status not in rule["from"]:
		frappe.throw(_("{0} is not possible while the job is {1}.").format(rule["label"], _(job.status)))
	if not capacities(job, user) & rule["who"]:
		frappe.throw(_("You are not allowed to {0} this job.").format(rule["label"]), frappe.PermissionError)
	if action in REASON_REQUIRED and not (reason or "").strip():
		frappe.throw(_("A reason is required to {0}.").format(rule["label"]))

	problem = _job_check(job, action)
	if problem:
		frappe.throw(_("Cannot {0}: {1}.").format(rule["label"], problem))

	before = job.status
	if action == "block":
		job.previous_status = before
		to = "Blocked"
	elif action == "unblock":
		to = job.previous_status or PATHS[job.job_type][1]
		job.previous_status = None
	else:
		to = rule["to"]

	job.status = to
	_log(job, user, action, before, to, reason)
	_save(job)
	return job.status


# ---------------------------------------------------------------------------------------------
# Machine-level actions


def _device_rules() -> dict:
	# Built per call so labels are translated in the current site's language.
	return {
		"start": {
			"from": {"Pending"},
			"to": "In Progress",
			"who": {TECHNICIAN_CAP},
			"label": _("Start Machine"),
		},
		"complete": {
			"from": {"In Progress"},
			"to": "Completed",
			"who": {TECHNICIAN_CAP},
			"label": _("Complete Machine"),
		},
		"block": {
			"from": {"Pending", "In Progress"},
			"to": "Blocked",
			"who": {TECHNICIAN_CAP, APPROVER_CAP},
			"label": _("Block Machine"),
		},
		"unblock": {
			"from": {"Blocked"},
			"to": "In Progress",
			"who": {APPROVER_CAP},
			"label": _("Unblock Machine"),
		},
		"cancel": {
			"from": {"Pending", "In Progress", "Blocked"},
			"to": "Cancelled",
			"who": {APPROVER_CAP},
			"label": _("Cancel Machine"),
		},
	}


def get_device_actions(job, user: str | None = None) -> dict[str, list[dict]]:
	user = user or frappe.session.user
	if job.status not in WORKING:
		return {}
	caps = capacities(job, user)
	out = {}
	for row in job.devices:
		allowed = [
			{"action": action, "label": rule["label"], "reason_required": action in REASON_REQUIRED}
			for action, rule in _device_rules().items()
			if row.device_status in rule["from"] and caps & rule["who"]
		]
		if allowed:
			out[row.name] = allowed
	return out


def apply_device_action(
	job_name: str, device: str, action: str, reason: str | None = None, user: str | None = None
) -> str:
	user = user or frappe.session.user
	job = frappe.get_doc(JOB, job_name)
	job.check_permission("read")

	rule = _device_rules().get(action)
	if not rule:
		frappe.throw(_("Unknown machine action {0}.").format(action))
	row = next((r for r in job.devices if r.name == device), None)
	if not row:
		frappe.throw(_("Machine {0} is not on job {1}.").format(device, job.name))
	if job.status not in WORKING:
		frappe.throw(_("Machines cannot be updated while the job is {0}.").format(_(job.status)))
	if row.device_status not in rule["from"]:
		frappe.throw(
			_("{0} is not possible while machine {1} is {2}.").format(
				rule["label"], _device_label(row), _(row.device_status)
			)
		)
	if not capacities(job, user) & rule["who"]:
		frappe.throw(_("You are not allowed to {0}.").format(rule["label"]), frappe.PermissionError)
	if action in REASON_REQUIRED and not (reason or "").strip():
		frappe.throw(_("A reason is required to {0}.").format(rule["label"]))
	if action == "complete" and not row.serial_no:
		frappe.throw(
			_("Machine {0} needs a Serial No before it can be completed.").format(_device_label(row))
		)
	if action == "complete" and _checklist_not_submitted(job, row):
		frappe.throw(
			_("Submit the checklist of machine {0} before completing it.").format(_device_label(row))
		)

	before = row.device_status
	row.device_status = rule["to"]
	_log(job, user, f"machine: {action}", before, row.device_status, reason, device=_device_label(row))
	_save(job)
	return row.device_status


# ---------------------------------------------------------------------------------------------


def _checklist_not_submitted(job, row) -> bool:
	"""A machine that has a checklist for this job type is completed only once that checklist is submitted."""
	if not card_for(job.job_type, row.item_code):
		return False
	form = form_for_device(job.name, row.name)
	return not form or form[2] != 1


def _device_label(row) -> str:
	return f"{row.item_code} / {row.serial_no}" if row.serial_no else f"{row.item_code} (row {row.idx})"


def _log(job, user, action, before, to, reason=None, device=None):
	job.append(
		"status_log",
		{
			"timestamp": now_datetime(),
			"user": user,
			"action": action,
			"from_status": before,
			"to_status": to,
			"device": device,
			"reason": (reason or "").strip() or None,
		},
	)


def _save(job):
	# Role and state rules were checked above; the save itself only writes status and log.
	job.flags.allow_status_change = True
	job.save(ignore_permissions=True)
