"""Delivery Note handoff to installation jobs (#16 / #43). Read-only on the Delivery Note itself.

- A later delivery of the same sales order adds its machines to the open Installation job that
  holds the order's earlier delivery, so one job follows the whole order (partial deliveries).
- A return, or a cancelled delivery, flags the affected machines on the job (``source_issue``) for a
  supervisor to decide; nothing is cancelled automatically (owner decision, 2026-10-20).
"""

import frappe
from frappe import _

from deployops.integrations import erpnext_sources

JOB = "DeployOps Job"
DEVICE = "DeployOps Job Device"
DELIVERY_NOTE = erpnext_sources.DELIVERY_NOTE
CLOSED = ("Completed", "Cancelled")


def on_delivery_note_submit(doc, method=None):
	_guarded(doc, flag_returned_machines if doc.is_return else add_to_open_job)


def on_delivery_note_cancel(doc, method=None):
	if doc.is_return:
		_guarded(doc, lambda d: clear_issue(_("Returned on {0}").format(d.name)))
	else:
		_guarded(doc, flag_cancelled_delivery)


def _guarded(doc, handler):
	"""A Delivery Note must never fail because of DeployOps: errors are logged, not raised."""
	point = "deployops_delivery_handoff"
	messages = len(frappe.local.message_log)
	frappe.db.savepoint(point)
	try:
		handler(doc)
	except Exception:
		frappe.db.rollback(save_point=point)
		del frappe.local.message_log[messages:]  # the delivery user should not see a job's error
		frappe.log_error(title=f"DeployOps delivery handoff failed for {doc.name}")
	else:
		frappe.db.release_savepoint(point)


def _save(job, comment: str):
	job.flags.delivery_handoff = True
	job.save(ignore_permissions=True)
	job.add_comment("Info", comment)


def open_job_for_order(doc):
	"""The open Installation job holding an earlier delivery of the same order(s) and customer."""
	orders = erpnext_sources.delivery_orders(doc.name)
	if not orders:
		return None
	earlier = frappe.get_all(
		"Delivery Note Item",
		filters={"against_sales_order": ["in", list(orders)], "parent": ["!=", doc.name], "docstatus": 1},
		pluck="parent",
		distinct=True,
	)
	if not earlier:
		return None
	name = frappe.db.get_value(
		JOB,
		{
			"job_type": "Installation",
			"source_doctype": DELIVERY_NOTE,
			"source_name": ["in", earlier],
			"customer": doc.customer,
			"status": ["not in", CLOSED],
		},
		"name",
		order_by="creation desc",
	)
	if not name:
		return None
	# P2a guard: confirm the found job's source DN shares at least one SO with the current DN.
	# Two concurrent orders for the same customer must not cross-contaminate: a DN that only
	# covers SO-001 must never absorb machines from a DN that only covers SO-002.
	job = frappe.get_doc(JOB, name)
	earlier_dn_orders = erpnext_sources.delivery_orders(job.source_name)
	if not (orders & earlier_dn_orders):
		return None
	return job


def add_to_open_job(doc):
	job = open_job_for_order(doc)
	if not job:
		return
	on_job = {row.serial_no for row in job.devices if row.serial_no}
	serialized = set(
		frappe.get_all(
			"Item",
			filters={"name": ["in", [row.item_code for row in doc.items] or [""]], "has_serial_no": 1},
			pluck="name",
		)
	)
	new = [
		{"item_code": line["item_code"], "serial_no": serial_no, "delivery_note": doc.name}
		for line in erpnext_sources.get_equipment_lines(doc)
		if line["item_code"] in serialized
		for serial_no in line["serial_nos"]
		if serial_no not in on_job
	]
	if not new:
		return
	if job.status == "Pending Review":
		job.add_comment(
			"Info",
			_(
				"Delivery Note {0} delivered {1} more machine(s); not added because the job is waiting for review."
			).format(doc.name, len(new)),
		)
		return
	# P2b: add devices one at a time so a single failed device does not block the rest.
	added = []
	skipped = []
	for row in new:
		job.append("devices", row)
		job.flags.delivery_handoff = True
		try:
			job.save(ignore_permissions=True)
			added.append(row["serial_no"])
		except frappe.ValidationError as e:
			# Discard the failed append and continue with the next device.
			job.reload()
			skipped.append((row["serial_no"], str(e)))
	parts = []
	if added:
		parts.append(_("{0} machine(s) added").format(len(added)))
	if skipped:
		detail = "; ".join("{0}: {1}".format(s, r) for s, r in skipped)
		parts.append(_("{0} skipped ({1})").format(len(skipped), detail))
	if parts:
		job.add_comment("Info", _("Delivery Note {0}: {1}.").format(doc.name, ", ".join(parts)))


def _open_rows(filters: dict) -> dict[str, list[str]]:
	"""Open-job machine rows matching the filters, grouped by job."""
	rows = frappe.get_all(DEVICE, filters={"parenttype": JOB, **filters}, fields=["name", "parent"])
	jobs: dict[str, list[str]] = {}
	for row in rows:
		if frappe.db.get_value(JOB, row.parent, "status") not in CLOSED:
			jobs.setdefault(row.parent, []).append(row.name)
	return jobs


def _flag(jobs: dict[str, list[str]], issue: str, comment: str):
	for job_name, rows in jobs.items():
		job = frappe.get_doc(JOB, job_name)
		for row in job.devices:
			if row.name in rows:
				row.source_issue = issue
		_save(job, comment)


def flag_returned_machines(doc):
	if not doc.return_against:
		return
	serials = [s for line in erpnext_sources.get_equipment_lines(doc) for s in line["serial_nos"]]
	if not serials:
		return
	issue = _("Returned on {0}").format(doc.name)
	_flag(
		_open_rows({"serial_no": ["in", serials], "delivery_note": doc.return_against}),
		issue,
		_("{0}: a supervisor decides what happens to the returned machine(s).").format(issue),
	)


def flag_cancelled_delivery(doc):
	issue = _("Delivery Note {0} was cancelled").format(doc.name)
	_flag(
		_open_rows({"delivery_note": doc.name}),
		issue,
		_("{0}: check the machines that came on it.").format(issue),
	)


def clear_issue(issue: str):
	jobs = _open_rows({"source_issue": issue})
	for job_name, rows in jobs.items():
		job = frappe.get_doc(JOB, job_name)
		for row in job.devices:
			if row.name in rows:
				row.source_issue = None
		_save(job, _("{0} was cancelled; the flag is cleared.").format(issue))
