"""DeployOps Job (#18 / #39): one intervention on one or more devices, started from an ERPNext source."""

import frappe
from frappe import _
from frappe.model.document import Document

from deployops.api.sources import visible_lines
from deployops.equipment import allocations
from deployops.integrations import erpnext_sources
from deployops.roles import TECHNICIAN
from deployops.security.equipment_access import get_allowed_items, get_category_items, is_unrestricted

PRE_INSTALLATION = "Pre-installation"
INSTALLATION = "Installation"
MAINTENANCE = "Maintenance"
SERIAL_REQUIRED = (INSTALLATION, MAINTENANCE)
CLOSED_STATUSES = ("Completed", "Cancelled")


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
			self.status = "Draft"
			self.set_source_details(snapshot)
			if not self.devices:
				for device in devices_from_source(source, snapshot):
					self.append("devices", device)
		else:
			self.validate_not_closed()
			self.validate_status_unchanged()
			self.validate_workflow_fields_unchanged()

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

		saved_log = frappe.get_all(
			"DeployOps Job Status Log",
			filters={"parent": self.name, "parenttype": "DeployOps Job"},
			pluck="name",
		)
		if sorted(row.name for row in self.status_log if row.name) != sorted(saved_log) or any(
			not row.name for row in self.status_log
		):
			frappe.throw(_("The status log can only be written by the job workflow."))

	def validate_devices(self, snapshot: dict):
		lines = list(snapshot["lines"])
		for note in self.later_deliveries():
			lines += erpnext_sources.get_equipment_lines(frappe.get_doc(erpnext_sources.DELIVERY_NOTE, note))
		source_items = {line["item_code"] for line in lines}
		source_serials = {}
		for line in lines:
			source_serials.setdefault(line["item_code"], set()).update(line["serial_nos"])

		# Rows already saved were checked when they were added; their delivery may since have been
		# cancelled or returned (flagged by delivery_handoff), which must not block later saves.
		saved = {}
		if not self.is_new():
			saved = {
				r.name: (r.item_code, r.serial_no or None)
				for r in frappe.get_all(
					"DeployOps Job Device",
					filters={"parent": self.name, "parenttype": "DeployOps Job"},
					fields=["name", "item_code", "serial_no"],
				)
			}

		seen = set()
		for row in self.devices:
			unchanged = saved.get(row.name) == (row.item_code, row.serial_no or None)
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

			if self.source_doctype == erpnext_sources.SUBSCRIPTION:
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
		serials = [row.serial_no for row in self.devices if row.serial_no]
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

		if not frappe.db.get_value("User", user, "enabled"):
			frappe.throw(_("Assigned technician {0} is not an active user.").format(user))
		if TECHNICIAN not in frappe.get_roles(user):
			frappe.throw(_("Assigned technician {0} does not have the {1} role.").format(user, TECHNICIAN))

		allowed = get_allowed_items(user)
		for row in self.devices:
			if row.item_code not in allowed:
				frappe.throw(
					_("Assigned technician {0} is not authorised for equipment {1}.").format(
						user, row.item_code
					)
				)


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
