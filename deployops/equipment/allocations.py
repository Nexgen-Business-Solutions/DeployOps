"""Serialized equipment allocation (#14 / #38): which machine is promised to or placed with whom.

One *active* allocation (Reserved or Deployed) per serial, enforced by a unique index on
`active_serial`. DeployOps never creates or edits stock entries; ERPNext keeps the stock ledger.

Rental: reserved in stock for a Subscription → Deployed when its Installation job is approved →
Returned (with condition) or Swapped Out for another machine.
Sale: reserved when a machine is picked on a job from a Sales Order → Delivered when ERPNext
delivers it (Delivery Note) → released if the job drops the machine or is cancelled.
"""

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime, nowdate

from deployops.integrations import erpnext_sources
from deployops.roles import ADMINISTRATOR, MANAGER, SUPERVISOR

ALLOCATION = "DeployOps Equipment Allocation"
ACTIVE = ("Reserved", "Deployed")
RENTAL, SALE = "Rental", "Sale"
HANDLER_ROLES = {SUPERVISOR, MANAGER}  # reserve, return, swap
CANCEL_ROLES = {MANAGER, ADMINISTRATOR}


def get_active(serial_no: str):
	name = frappe.db.get_value(ALLOCATION, {"active_serial": serial_no})
	return frappe.get_doc(ALLOCATION, name) if name else None


def is_in_stock(serial_no: str) -> bool:
	status, warehouse, customer = frappe.db.get_value(
		"Serial No", serial_no, ["status", "warehouse", "customer"]
	) or (None, None, None)
	return status == "Active" and bool(warehouse) and not customer


def add_event(doc, event: str, note: str | None = None, job: str | None = None, reference=None):
	doc.append(
		"events",
		{
			"timestamp": now_datetime(),
			"user": frappe.session.user,
			"event": event,
			"job": job,
			"reference_doctype": reference[0] if reference else None,
			"reference_name": reference[1] if reference else None,
			"note": (note or "").strip() or None,
		},
	)


def set_status(doc, status: str):
	doc.status = status
	doc.active_serial = doc.serial_no if status in ACTIVE else None


def save_system(doc):
	"""Save a status change made by these functions (checks were done before)."""
	doc.flags.allow_status_change = True
	doc.save(ignore_permissions=True)


def require_role(roles: set[str], label: str):
	if frappe.session.user != "Administrator" and not roles & set(frappe.get_roles()):
		frappe.throw(_("You are not allowed to {0}.").format(label), frappe.PermissionError)


# ---------------------------------------------------------------------------------------------
# Manual actions (Supervisor / Manager / Admin)


def reserve(
	serial_no: str,
	source_doctype: str,
	source_name: str,
	company: str | None = None,
	system: bool = False,
	**extra,
):
	"""Create a Reserved allocation; checks run in the DocType's validate.

	system=True is for reservations DeployOps makes itself (a machine picked on a job), which the
	user's role may not be allowed to create directly.
	"""
	doc = frappe.get_doc(
		{
			"doctype": ALLOCATION,
			"allocation_type": RENTAL if source_doctype == erpnext_sources.SUBSCRIPTION else SALE,
			"serial_no": serial_no,
			"source_doctype": source_doctype,
			"source_name": source_name,
			"company": company or frappe.db.get_value(source_doctype, source_name, "company"),
			**extra,
		}
	)
	doc.flags.from_allocation_actions = True  # lets reserved_by_job / replaces through
	doc.insert(ignore_permissions=system)
	return doc


def return_allocation(name: str, condition: str, returned_on: str | None = None):
	require_role(HANDLER_ROLES, _("record a return"))
	doc = frappe.get_doc(ALLOCATION, name)
	doc.check_permission("read")
	if doc.allocation_type != RENTAL or doc.status != "Deployed":
		frappe.throw(
			_("Only a deployed rental machine can be returned (this one is {0}).").format(_(doc.status))
		)
	if not (condition or "").strip():
		frappe.throw(_("Describe the machine's condition on return."))

	doc.returned_on = getdate(returned_on or nowdate())
	doc.return_condition = condition.strip()
	set_status(doc, "Returned")
	add_event(doc, "Returned", condition)
	save_system(doc)
	return doc.status


def swap(name: str, new_serial_no: str, condition: str):
	"""Take a deployed rental machine back and reserve a replacement for the same subscription."""
	require_role(HANDLER_ROLES, _("swap a machine"))
	old = frappe.get_doc(ALLOCATION, name)
	old.check_permission("read")
	if old.allocation_type != RENTAL or old.status != "Deployed":
		frappe.throw(
			_("Only a deployed rental machine can be swapped (this one is {0}).").format(_(old.status))
		)
	if not (condition or "").strip():
		frappe.throw(_("Describe the condition of the machine being swapped out."))

	old.returned_on = getdate(nowdate())
	old.return_condition = condition.strip()
	set_status(old, "Swapped Out")
	add_event(old, "Swapped Out", condition)
	save_system(old)

	new = reserve(new_serial_no, old.source_doctype, old.source_name, old.company, replaces=old.name)
	old.reload()
	old.replaced_by = new.name
	add_event(old, "Replaced", _("Replaced by {0}").format(new_serial_no), reference=(ALLOCATION, new.name))
	save_system(old)
	return new.name


def cancel(name: str, reason: str):
	require_role(CANCEL_ROLES, _("cancel a reservation"))
	doc = frappe.get_doc(ALLOCATION, name)
	doc.check_permission("read")
	if doc.status != "Reserved":
		frappe.throw(_("Only a reservation can be cancelled; a deployed machine must be returned."))
	if not (reason or "").strip():
		frappe.throw(_("A reason is required to cancel a reservation."))

	doc.returned_on = getdate(nowdate())
	set_status(doc, "Cancelled")
	add_event(doc, "Cancelled", reason)
	save_system(doc)
	return doc.status


# ---------------------------------------------------------------------------------------------
# Automatic: jobs and deliveries


def sync_job(job):
	"""Keep allocations in line with a job after every save.

	- Sale (job from a Sales Order): each machine picked reserves its serial for the order's
	  customer; serials dropped from the job, cancelled machines and cancelled jobs release them.
	- Rental (Installation job from a Subscription): approval deploys the allocated machines.
	"""
	if job.source_doctype == erpnext_sources.SALES_ORDER:
		_sync_sale_reservations(job)
	elif (
		job.source_doctype == erpnext_sources.SUBSCRIPTION
		and job.job_type == "Installation"
		and job.status == "Completed"
	):
		_deploy_rental(job)


def _sync_sale_reservations(job):
	wanted = set()
	if job.status != "Cancelled":
		wanted = {row.serial_no for row in job.devices if row.serial_no and row.device_status != "Cancelled"}

	for serial_no in wanted:
		active = get_active(serial_no)
		if active:
			if active.source_doctype == job.source_doctype and active.source_name == job.source_name:
				continue  # already reserved for this order
			frappe.throw(
				_("Serial No {0} is already {1} for {2} ({3}).").format(
					serial_no, _(active.status).lower(), active.customer_name or active.customer, active.name
				)
			)
		if not is_in_stock(serial_no):
			delivered_to = frappe.db.get_value("Serial No", serial_no, "customer")
			if delivered_to and delivered_to == job.customer:
				continue  # already delivered to this customer: nothing to reserve
			frappe.throw(
				_("Serial No {0} is not in stock and cannot be reserved for this order.").format(serial_no)
			)
		reserve(
			serial_no, job.source_doctype, job.source_name, job.company, system=True, reserved_by_job=job.name
		)

	for name in frappe.get_all(
		ALLOCATION, filters={"reserved_by_job": job.name, "status": "Reserved"}, pluck="name"
	):
		doc = frappe.get_doc(ALLOCATION, name)
		if doc.serial_no not in wanted:
			set_status(doc, "Cancelled")
			doc.returned_on = getdate(nowdate())
			add_event(doc, "Released", _("No longer on job {0}").format(job.name), job=job.name)
			save_system(doc)


def _deploy_rental(job):
	for row in job.devices:
		if row.device_status != "Completed" or not row.serial_no:
			continue
		active = get_active(row.serial_no)
		if not active or active.source_name != job.source_name or active.status != "Reserved":
			continue
		active.deployed_on = getdate(nowdate())
		set_status(active, "Deployed")
		add_event(active, "Deployed", _("Installation approved"), job=job.name)
		save_system(active)


def on_delivery_note_submit(doc, method=None):
	"""ERPNext delivered machines: close their sale reservations as Delivered."""
	if doc.is_return:
		return
	dn_orders = erpnext_sources.delivery_orders(doc.name)
	for line in erpnext_sources.get_equipment_lines(doc):
		for serial_no in line["serial_nos"]:
			active = get_active(serial_no)
			if not active:
				continue
			if active.allocation_type == RENTAL:
				add_event(
					active,
					"Delivery Note",
					_("Shipped on {0}").format(doc.name),
					reference=(doc.doctype, doc.name),
				)
				save_system(active)
				continue
			# Sale: only transition when the DN delivers the same Sales Order and company as the allocation.
			if active.source_name not in dn_orders or doc.company != active.company:
				continue
			active.deployed_on = getdate(doc.posting_date)
			set_status(active, "Delivered")
			note = None if doc.customer == active.customer else _("Delivered to {0}").format(doc.customer)
			add_event(active, "Delivered", note, reference=(doc.doctype, doc.name))
			save_system(active)


def on_delivery_note_cancel(doc, method=None):
	"""A cancelled delivery puts its sale reservations back to Reserved."""
	if doc.is_return:
		return
	for name in frappe.get_all(
		"DeployOps Equipment Allocation Event",
		filters={"reference_doctype": doc.doctype, "reference_name": doc.name, "event": "Delivered"},
		pluck="parent",
	):
		allocation = frappe.get_doc(ALLOCATION, name)
		if allocation.status != "Delivered" or get_active(allocation.serial_no):
			continue
		allocation.deployed_on = None
		set_status(allocation, "Reserved")
		add_event(allocation, "Delivery cancelled", reference=(doc.doctype, doc.name))
		save_system(allocation)


def active_rental_serials(subscription: str) -> list[dict]:
	"""Machines currently allocated to a subscription (for its jobs' device rows)."""
	return frappe.get_all(
		ALLOCATION,
		filters={
			"source_doctype": erpnext_sources.SUBSCRIPTION,
			"source_name": subscription,
			"status": ["in", ACTIVE],
		},
		fields=["serial_no", "item_code"],
		order_by="creation",
	)


# ---------------------------------------------------------------------------------------------
# Serial history


def get_serial_history(serial_no: str, user: str | None = None) -> list[dict]:
	"""Everything that happened to one machine, oldest first: stock moves, allocations, jobs.

	Allocations and jobs are listed only when the user may read them (#12 visibility), so the
	history never shows another customer's job or allocation to someone outside it.
	ERPNext stock movements are shown to Supervisors, Managers and Administrators only, not
	Technicians, because warehouse and voucher references are outside their operational scope.
	"""
	from deployops.security.job_permissions import get_scope

	user = user or frappe.session.user
	rows = []

	if get_scope(user) != "assigned":  # stock moves for Supervisors+ only, not Technicians
		entry = frappe.qb.DocType("Serial and Batch Entry")
		bundle = frappe.qb.DocType("Serial and Batch Bundle")
		for move in (
		frappe.qb.from_(entry)
		.join(bundle)
		.on(entry.parent == bundle.name)
		.select(
			bundle.posting_datetime,
			bundle.voucher_type,
			bundle.voucher_no,
			bundle.type_of_transaction,
			bundle.warehouse,
		)
		.where(entry.serial_no == serial_no)
		.where(bundle.is_cancelled == 0)
		.where(bundle.docstatus == 1)
		.run(as_dict=True)
		):
			rows.append(
				{
					"when": move.posting_datetime,
					"source": "ERPNext",
					"event": _("Stock {0}").format(_(move.type_of_transaction)),
					"reference_doctype": move.voucher_type,
					"reference_name": move.voucher_no,
					"detail": move.warehouse,
				}
			)

	for name in frappe.get_all(ALLOCATION, filters={"serial_no": serial_no}, pluck="name"):
		allocation = frappe.get_doc(ALLOCATION, name)
		if not frappe.has_permission(ALLOCATION, "read", allocation, user=user):
			continue
		for event in allocation.events:
			rows.append(
				{
					"when": event.timestamp,
					"source": _("Allocation"),
					"event": f"{allocation.allocation_type}: {event.event}",
					"reference_doctype": ALLOCATION,
					"reference_name": allocation.name,
					"detail": " · ".join(filter_empty((allocation.customer_name, event.note, event.job))),
				}
			)

	job = frappe.qb.DocType("DeployOps Job")
	device = frappe.qb.DocType("DeployOps Job Device")
	for row in (
		frappe.qb.from_(device)
		.join(job)
		.on(device.parent == job.name)
		.select(job.name, job.creation, job.job_type, job.status, job.customer_name, device.device_status)
		.where(device.serial_no == serial_no)
		.where(device.parenttype == "DeployOps Job")
		.run(as_dict=True)
	):
		if not frappe.has_permission("DeployOps Job", "read", row.name, user=user):
			continue
		rows.append(
			{
				"when": row.creation,
				"source": _("Job"),
				"event": f"{row.job_type}: {row.status}",
				"reference_doctype": "DeployOps Job",
				"reference_name": row.name,
				"detail": " · ".join(
					filter_empty((row.customer_name, _("machine {0}").format(_(row.device_status))))
				),
			}
		)

	return sorted(rows, key=lambda r: str(r["when"] or ""))  # rows without a date come first


def filter_empty(values) -> list[str]:
	return [str(value) for value in values if value]
