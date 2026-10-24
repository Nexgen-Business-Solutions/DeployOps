"""DeployOps Job (#18 / #39): one intervention on one or more devices, started from an ERPNext source."""

import frappe
from frappe import _
from frappe.model.document import Document

from deployops.api.sources import visible_lines
from deployops.checklists.cards import form_for_device
from deployops.equipment import allocations
from deployops.integrations import erpnext_sources
from deployops.roles import TECHNICIAN
from deployops.security.equipment_access import get_allowed_items, get_category_items, is_unrestricted

PRE_INSTALLATION = "Pre-installation"
INSTALLATION = "Installation"
MAINTENANCE = "Maintenance"
JOB = "DeployOps Job"
DEVICE = "DeployOps Job Device"
SERIAL_REQUIRED = (INSTALLATION, MAINTENANCE)
CLOSED_STATUSES = ("Completed", "Cancelled")
# Fixed once the job exists: the source and the customer, contact and site copied from it.
SOURCE_FIELDS = (
	"company",
	"source_doctype",
	"source_name",
	"customer",
	"customer_name",
	"contact",
	"contact_display",
	"address",
	"address_display",
)
LOG_FIELDS = ("timestamp", "user", "action", "from_status", "to_status", "device", "reason")


class DeployOpsJob(Document):
	def validate(self):
		if self.is_new():
			source = erpnext_sources.validate_source(self.source_doctype, self.source_name, self.company)
		else:
			# Checked once, at creation: a source may later be closed or completed in ERPNext
			# (normal after delivery) without stopping the work on its job.
			source = frappe.get_doc(self.source_doctype, self.source_name)
		snapshot = erpnext_sources.get_source_snapshot(source)

		if self.is_new():
			if visible_lines(snapshot, frappe.session.user) is None:
				frappe.throw(
					_("You are not authorised for any equipment on {0} {1}.").format(
						_(self.source_doctype), self.source_name
					),
					frappe.PermissionError,
				)
			# A new job starts clean: Draft, no history, every machine Pending (only the workflow
			# writes statuses and the log).
			self.status = "Draft"
			self.previous_status = None
			self.set("status_log", [])
			self.set_source_details(snapshot)
			if not self.devices:
				for device in devices_from_source(source, snapshot):
					self.append("devices", device)
			for row in self.devices:
				row.device_status = "Pending"
				row.source_issue = None
		else:
			self.validate_not_closed()
			self.validate_status_unchanged()
			self.validate_fixed_fields()
			self.validate_workflow_fields_unchanged()
			self.validate_log_unchanged()

		for row in self.devices:
			# Rows added during validate miss Frappe's field defaults.
			row.device_status = row.device_status or "Pending"
			if self.source_doctype == erpnext_sources.DELIVERY_NOTE and not row.delivery_note:
				row.delivery_note = self.source_name

		self.validate_devices(snapshot)
		self.validate_equipment_access()
		self.validate_equipment_category()
		self.validate_no_double_booking()
		self.validate_assigned_technician()

	def on_update(self):
		# Reserve, release or deploy machines to match the job (#14).
		allocations.sync_job(self)

	def set_source_details(self, snapshot: dict):
		"""Customer, contact and site as confirmed on the source, kept as a read-only snapshot."""
		self.customer = snapshot["customer"]
		self.customer_name = snapshot["customer_name"]

		contact = snapshot["contact"] or {}
		self.contact = contact.get("name")
		details = (contact.get(f) for f in ("full_name", "email_id", "phone", "mobile_no"))
		self.contact_display = "\n".join(value for value in details if value)

		address = snapshot["address"] or {}
		self.address = address.get("name")
		self.address_display = address.get("display")

	def validate_not_closed(self):
		if self.flags.allow_status_change:
			return
		if frappe.db.get_value("DeployOps Job", self.name, "status") in ("Completed", "Cancelled"):
			frappe.throw(_("A completed or cancelled job cannot be changed."))

	def validate_status_unchanged(self):
		# Status changes only go through the job workflow (#19).
		if self.flags.allow_status_change:
			return
		if self.has_value_changed("status") or self.has_value_changed("previous_status"):
			frappe.throw(_("The job status can only be changed through the job workflow."))

	def validate_fixed_fields(self):
		for field in SOURCE_FIELDS:
			if self.has_value_changed(field):
				frappe.throw(
					_("{0} comes from the source and cannot be changed after the job is created.").format(
						_(self.meta.get_label(field))
					)
				)
		if self.has_value_changed("job_type") and frappe.db.get_value(JOB, self.name, "status") != "Draft":
			frappe.throw(_("The job type can only be changed while the job is Draft."))

	def validate_log_unchanged(self):
		"""Existing status-log entries never change; only the workflow appends new ones."""
		saved = {
			row.name: row
			for row in frappe.get_all(
				"DeployOps Job Status Log",
				filters={"parent": self.name, "parenttype": JOB},
				fields=["name", *LOG_FIELDS],
			)
		}
		current = {row.name: row for row in self.status_log if row.name in saved}
		if set(current) != set(saved):
			frappe.throw(_("The status log can only be written by the job workflow."))
		for name, before in saved.items():
			row = current[name]
			if any(str(row.get(f) or "") != str(before.get(f) or "") for f in LOG_FIELDS):
				frappe.throw(_("Status log entries cannot be changed."))
		added = [row for row in self.status_log if row.name not in saved]
		if added and not self.flags.allow_status_change:
			frappe.throw(_("The status log can only be written by the job workflow."))

	def changed_rows(self) -> list:
		"""Machine rows that are new, or whose Item or serial differs from the saved job."""
		saved = {}
		if not self.is_new():
			saved = {
				r.name: (r.item_code, r.serial_no or None)
				for r in frappe.get_all(
					DEVICE,
					filters={"parent": self.name, "parenttype": JOB},
					fields=["name", "item_code", "serial_no"],
				)
			}
		return [row for row in self.devices if saved.get(row.name) != (row.item_code, row.serial_no or None)]

	def validate_workflow_fields_unchanged(self):
		"""Machine statuses and the status log are only written by the workflow."""
		if self.flags.allow_status_change:
			return

		saved_status = frappe.db.get_value("DeployOps Job", self.name, "status")
		saved = {
			row.name: row
			for row in frappe.get_all(
				"DeployOps Job Device",
				filters={"parent": self.name, "parenttype": "DeployOps Job"},
				fields=["name", "item_code", "serial_no", "device_status", "delivery_note", "source_issue"],
			)
		}
		current = {row.name: row for row in self.devices if row.name}

		removed = set(saved) - set(current)
		if removed and saved_status != "Draft":
			frappe.throw(
				_("Machines can only be removed while the job is Draft; use Cancel Machine instead.")
			)

		for row in self.devices:
			before = saved.get(row.name)
			if not before:
				if saved_status == "Pending Review":
					frappe.throw(_("Machines cannot be added while the job is waiting for review."))
				row.device_status = "Pending"
				continue
			if row.device_status != before.device_status:
				frappe.throw(_("Machine status can only be changed through the job workflow."))
			if not self.flags.delivery_handoff and (
				(row.delivery_note or None) != (before.delivery_note or None)
				or (row.source_issue or None) != (before.source_issue or None)
			):
				frappe.throw(_("Row #{0}: the delivery details are set by the system.").format(row.idx))
			changed = (row.item_code, row.serial_no or None) != (before.item_code, before.serial_no or None)
			form = form_for_device(self.name, row.name) if changed else None
			first_serial_on_draft = (
				form and form[2] == 0 and row.item_code == before.item_code and not before.serial_no
			)  # #22: a pre-installation may start before the machine is picked
			if form and not first_serial_on_draft:
				frappe.throw(
					_(
						"Row #{0}: this machine has a checklist; a manager must cancel it before the machine can be changed."
					).format(row.idx)
				)
			if changed and (
				saved_status == "Pending Review" or before.device_status in ("Completed", "Cancelled")
			):
				frappe.throw(
					_("Row #{0}: a {1} machine cannot be changed.").format(
						row.idx,
						_("completed or cancelled")
						if before.device_status in ("Completed", "Cancelled")
						else _("submitted"),
					)
				)

	def validate_devices(self, snapshot: dict):
		lines = list(snapshot["lines"])
		for note in self.later_deliveries():
			lines += erpnext_sources.get_equipment_lines(frappe.get_doc(erpnext_sources.DELIVERY_NOTE, note))
		source_items = {line["item_code"] for line in lines}
		source_serials = {}
		for line in lines:
			source_serials.setdefault(line["item_code"], set()).update(line["serial_nos"])

		# Rows already saved were checked when they were added; since then their delivery may have
		# been cancelled or returned, or their rental machine returned, which must not block later
		# saves (e.g. a Manager cancelling the job).
		changed = {id(row) for row in self.changed_rows()}

		seen = set()
		for row in self.devices:
			unchanged = id(row) not in changed
			if not frappe.db.get_value("Item", row.item_code, "has_serial_no"):
				frappe.throw(
					_("Row #{0}: Item {1} is not serial-numbered equipment.").format(row.idx, row.item_code)
				)

			if self.source_doctype != erpnext_sources.SUBSCRIPTION and row.item_code not in source_items:
				frappe.throw(
					_("Row #{0}: Item {1} is not on {2} {3}.").format(
						row.idx, row.item_code, _(self.source_doctype), self.source_name
					)
				)

			if not row.serial_no:
				if self.job_type in SERIAL_REQUIRED:
					frappe.throw(
						_("Row #{0}: a Serial No is required for {1} jobs.").format(row.idx, _(self.job_type))
					)
				continue

			if row.serial_no in seen:
				frappe.throw(
					_("Row #{0}: Serial No {1} is listed more than once.").format(row.idx, row.serial_no)
				)
			seen.add(row.serial_no)

			erpnext_sources.validate_serial(row.serial_no, row.item_code, self.company)

			if self.source_doctype == erpnext_sources.SUBSCRIPTION and not unchanged:
				allocated = {r.serial_no for r in allocations.active_rental_serials(self.source_name)}
				if row.serial_no not in allocated:
					frappe.throw(
						_(
							"Row #{0}: Serial No {1} is not allocated to subscription {2}; reserve it first."
						).format(row.idx, row.serial_no, self.source_name)
					)

			listed = source_serials.get(row.item_code)
			if listed and row.serial_no not in listed and not unchanged:
				frappe.throw(
					_("Row #{0}: Serial No {1} is not on {2} {3}.").format(
						row.idx, row.serial_no, _(self.source_doctype), self.source_name
					)
				)

		if self.source_doctype != erpnext_sources.SUBSCRIPTION and changed:
			self.validate_quantities(lines)
		if self.source_doctype == erpnext_sources.SALES_ORDER and changed:
			self.validate_order_serials()

	def validate_quantities(self, lines: list[dict]):
		"""No more machines of an Item than the source covers (ordered units, or listed serials)."""
		allowed: dict[str, int] = {}
		for line in lines:
			units = max(int(line.get("qty") or 1), len(line["serial_nos"]))
			allowed[line["item_code"]] = allowed.get(line["item_code"], 0) + units
		counts: dict[str, int] = {}
		for row in self.devices:
			if row.device_status != "Cancelled":
				counts[row.item_code] = counts.get(row.item_code, 0) + 1
		for item_code, count in counts.items():
			if count > allowed.get(item_code, 0):
				frappe.throw(
					_("{0} {1} covers {2} unit(s) of {3}; this job lists {4}.").format(
						_(self.source_doctype), self.source_name, allowed.get(item_code, 0), item_code, count
					)
				)

	def validate_order_serials(self):
		"""Units an order has already delivered keep their delivered serials; only the rest of the
		order may use machines from stock (#39)."""
		delivered_by_item = erpnext_sources.get_delivered_serials(self.source_name)
		for item_code in {row.item_code for row in self.devices}:
			delivered = set(delivered_by_item.get(item_code, []))
			if not delivered:
				continue
			_choices, stock_units = serial_choices(self.source_doctype, self.source_name, item_code)
			others = [
				row
				for row in self.devices
				if row.item_code == item_code
				and row.device_status != "Cancelled"
				and row.serial_no not in delivered
			]
			if len(others) > stock_units:
				frappe.throw(
					_(
						"Sales Order {0} has delivered {1} unit(s) of {2} ({3}); delivered machines must use their delivered serials."
					).format(self.source_name, len(delivered), item_code, ", ".join(sorted(delivered)))
				)

	def later_deliveries(self) -> list[str]:
		"""Other Delivery Notes whose machines were added to this job (#16): they must be submitted
		deliveries of the same sales order(s) to the same customer."""
		if self.source_doctype != erpnext_sources.DELIVERY_NOTE:
			return []
		notes = {row.delivery_note for row in self.devices if row.delivery_note} - {self.source_name}
		saved = set()
		if not self.is_new():
			saved = set(
				frappe.get_all(
					"DeployOps Job Device",
					filters={"parent": self.name, "parenttype": "DeployOps Job"},
					pluck="delivery_note",
				)
			)
		orders = erpnext_sources.delivery_orders(self.source_name)
		for note in notes - saved:  # deliveries already on the job were checked when added
			doc = frappe.db.get_value(
				erpnext_sources.DELIVERY_NOTE, note, ["docstatus", "is_return", "customer"], as_dict=True
			)
			if (
				not doc
				or doc.docstatus != 1
				or doc.is_return
				or doc.customer != self.customer
				or not orders & erpnext_sources.delivery_orders(note)
			):
				frappe.throw(_("Delivery Note {0} is not a delivery of this job's order.").format(note))
		return sorted(notes)

	def validate_equipment_access(self):
		user = frappe.session.user
		if self.flags.delivery_handoff or is_unrestricted(user):
			return  # the system adding delivered machines; the technician is still checked below

		allowed = get_allowed_items(user)
		for row in self.devices:
			if row.item_code not in allowed:
				frappe.throw(
					_("Row #{0}: you are not authorised for equipment {1}.").format(row.idx, row.item_code),
					frappe.PermissionError,
				)

	def validate_equipment_category(self):
		if not self.equipment_category:
			return

		items = get_category_items([self.equipment_category])
		for row in self.devices:
			if row.item_code not in items:
				frappe.throw(
					_("Row #{0}: Item {1} is not in equipment category {2}.").format(
						row.idx, row.item_code, self.equipment_category
					)
				)

	def validate_no_double_booking(self):
		# A cancelled machine no longer holds its serial, here or on another job.
		serials = [
			row.serial_no for row in self.devices if row.serial_no and row.device_status != "Cancelled"
		]
		if not serials:
			return

		job = frappe.qb.DocType("DeployOps Job")
		device = frappe.qb.DocType("DeployOps Job Device")
		clash = (
			frappe.qb.from_(device)
			.join(job)
			.on(device.parent == job.name)
			.select(device.serial_no, job.name)
			.where(device.parenttype == "DeployOps Job")
			.where(device.serial_no.isin(serials))
			.where(device.device_status != "Cancelled")
			.where(job.name != (self.name or ""))
			.where(job.job_type == self.job_type)
			.where(job.status.notin(CLOSED_STATUSES))
			.limit(1)
			.run(as_dict=True)
		)
		if clash:
			frappe.throw(
				_("Serial No {0} is already on open {1} job {2}.").format(
					clash[0].serial_no, _(self.job_type), clash[0].name
				)
			)

	def validate_assigned_technician(self):
		user = self.assigned_technician
		if not user:
			return
		if (
			not self.is_new()
			and not self.has_value_changed("assigned_technician")
			and not self.changed_rows()
		):
			# Checked when assigned and when machines change. Revoking the technician's access later
			# hides the job from them (#12) but must not stop a Manager from cancelling or reassigning.
			return

		if not frappe.db.get_value("User", user, "enabled"):
			frappe.throw(_("Assigned technician {0} is not an active user.").format(user))
		if TECHNICIAN not in frappe.get_roles(user):
			frappe.throw(_("Assigned technician {0} does not have the {1} role.").format(user, TECHNICIAN))

		allowed = get_allowed_items(user)
		for row in self.devices:
			if row.device_status != "Cancelled" and row.item_code not in allowed:
				frappe.throw(
					_("Assigned technician {0} is not authorised for equipment {1}.").format(
						user, row.item_code
					)
				)


def serial_choices(
	source_doctype: str, source_name: str, item_code: str, delivery_note: str | None = None
) -> tuple[list[str] | None, int]:
	"""Serials a machine of this Item may use on a job from this source, and how many units may
	still come from stock. ``None`` means the source does not decide (maintenance sources).

	- Delivery Note (or the row's own later delivery, #16): its serials only.
	- Subscription: the machines allocated to it (#14).
	- Sales Order: serials already delivered on the order, then any reserved for it; stock only
	  for units not delivered yet.
	"""
	if delivery_note or source_doctype == erpnext_sources.DELIVERY_NOTE:
		note = frappe.get_doc(erpnext_sources.DELIVERY_NOTE, delivery_note or source_name)
		lines = erpnext_sources.get_equipment_lines(note)
		return [s for line in lines if line["item_code"] == item_code for s in line["serial_nos"]], 0

	if source_doctype == erpnext_sources.SUBSCRIPTION:
		return [
			r.serial_no for r in allocations.active_rental_serials(source_name) if r.item_code == item_code
		], 0

	if source_doctype == erpnext_sources.SALES_ORDER:
		delivered = erpnext_sources.get_delivered_serials(source_name).get(item_code, [])
		reserved = frappe.get_all(
			"DeployOps Equipment Allocation",
			filters={
				"source_doctype": source_doctype,
				"source_name": source_name,
				"item_code": item_code,
				"status": "Reserved",
			},
			pluck="serial_no",
			order_by="creation",
		)
		ordered = sum(
			int(qty or 0)
			for qty in frappe.get_all(
				"Sales Order Item",
				filters={"parent": source_name, "parenttype": source_doctype, "item_code": item_code},
				pluck="qty",
			)
		)
		return delivered + [s for s in reserved if s not in delivered], max(0, ordered - len(delivered))

	return None, 0


def devices_from_source(source, snapshot: dict, user: str | None = None) -> list[dict]:
	"""Device rows for a new job, used both on save and when the source is picked in the form.

	One row per machine: per serial when the source lists serials; otherwise per unit ordered,
	with the serial taken from the order's deliveries when it has already been delivered.
	Only serial-numbered Items within the user's equipment profile are included.
	"""
	user = user or frappe.session.user
	item_codes = [line["item_code"] for line in snapshot["lines"]]
	serialized = set(
		frappe.get_all("Item", filters={"name": ["in", item_codes or [""]], "has_serial_no": 1}, pluck="name")
	)
	allowed = None if is_unrestricted(user) else get_allowed_items(user)
	if source.doctype == erpnext_sources.SUBSCRIPTION:
		# A subscription bills a service; its machines are the ones allocated to it (#14).
		return [
			{"item_code": row.item_code, "serial_no": row.serial_no}
			for row in allocations.active_rental_serials(source.name)
			if allowed is None or row.item_code in allowed
		]

	delivered = {}
	if source.doctype == erpnext_sources.SALES_ORDER:
		delivered = erpnext_sources.get_delivered_serials(source.name)
		for row in frappe.get_all(
			"DeployOps Equipment Allocation",
			filters={"source_doctype": source.doctype, "source_name": source.name, "status": "Reserved"},
			fields=["item_code", "serial_no"],
			order_by="creation",
		):
			delivered.setdefault(row.item_code, []).append(row.serial_no)

	devices = []
	for line in snapshot["lines"]:
		item_code = line["item_code"]
		if item_code not in serialized or (allowed is not None and item_code not in allowed):
			continue

		if line["serial_nos"]:
			devices.extend(
				{"item_code": item_code, "serial_no": serial_no} for serial_no in line["serial_nos"]
			)
			continue

		available = delivered.get(item_code, [])
		for _unit in range(int(line["qty"] or 1)):
			devices.append({"item_code": item_code, "serial_no": available.pop(0) if available else None})

	return devices
