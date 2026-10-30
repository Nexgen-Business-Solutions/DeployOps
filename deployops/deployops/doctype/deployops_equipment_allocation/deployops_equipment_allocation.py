"""DeployOps Equipment Allocation (#14 / #38): one machine promised to or placed with one customer."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate

from deployops.equipment.allocations import RENTAL, SALE, add_event, get_active, is_in_stock, set_status
from deployops.integrations import erpnext_sources
from deployops.security.equipment_access import get_allowed_items, is_unrestricted

SOURCE_FOR_TYPE = {RENTAL: erpnext_sources.SUBSCRIPTION, SALE: erpnext_sources.SALES_ORDER}
WORKFLOW_FIELDS = (
	"customer",
	"customer_name",
	"item_code",
	"status",
	"active_serial",
	"reserved_on",
	"deployed_on",
	"returned_on",
	"return_condition",
	"replaces",
	"replaced_by",
	"reserved_by_job",
	"serial_no",
	"source_name",
	"source_doctype",
	"allocation_type",
	"company",
)


class DeployOpsEquipmentAllocation(Document):
	def validate(self):
		if self.is_new():
			self.validate_new_reservation()
		elif not self.flags.allow_status_change:
			self.validate_workflow_fields_unchanged()

	def validate_new_reservation(self):
		if SOURCE_FOR_TYPE[self.allocation_type] != self.source_doctype:
			frappe.throw(
				_("A {0} allocation must come from a {1}.").format(
					_(self.allocation_type), _(SOURCE_FOR_TYPE[self.allocation_type])
				)
			)

		if not self.flags.from_allocation_actions:
			# Set only by DeployOps (a job's reservation, a swap), never by the client.
			self.reserved_by_job = self.replaces = None

		source = erpnext_sources.validate_source(self.source_doctype, self.source_name, self.company)
		serial = erpnext_sources.validate_serial(self.serial_no, company=self.company)
		self.item_code = serial.item_code
		if not frappe.db.get_value("Item", self.item_code, "has_serial_no"):
			frappe.throw(_("Item {0} is not serial-numbered equipment.").format(self.item_code))

		if self.allocation_type == SALE:
			ordered = {line["item_code"] for line in erpnext_sources.get_equipment_lines(source)}
			if self.item_code not in ordered:
				frappe.throw(_("Item {0} is not on {1}.").format(self.item_code, self.source_name))

		if not is_unrestricted(frappe.session.user) and self.item_code not in get_allowed_items():
			frappe.throw(
				_("You are not authorised for equipment {0}.").format(self.item_code), frappe.PermissionError
			)

		active = get_active(self.serial_no)
		if active:
			frappe.throw(
				_("Serial No {0} is already {1} for {2} ({3}).").format(
					self.serial_no,
					_(active.status).lower(),
					active.customer_name or active.customer,
					active.name,
				)
			)
		if not is_in_stock(self.serial_no):
			frappe.throw(_("Serial No {0} is not in stock, so it cannot be reserved.").format(self.serial_no))

		snapshot = erpnext_sources.get_source_snapshot(source)
		self.customer = snapshot["customer"]
		self.customer_name = snapshot["customer_name"]
		self.reserved_on = getdate(nowdate())
		self.deployed_on = self.returned_on = self.return_condition = self.replaced_by = None
		self.events = []
		set_status(self, "Reserved")
		add_event(
			self,
			"Reserved",
			_("Replaces {0}").format(self.replaces) if self.replaces else None,
			job=self.reserved_by_job,
			reference=(self.source_doctype, self.source_name),
		)

	def validate_workflow_fields_unchanged(self):
		before = self.get_doc_before_save()
		if any(self.get(field) != before.get(field) for field in WORKFLOW_FIELDS):
			frappe.throw(
				_(
					"Allocation customer, item, status and dates change only through Reserve, Return, Swap and Cancel."
				)
			)
		if [row.name for row in self.events] != [row.name for row in before.events]:
			frappe.throw(_("The movement log can only be written by DeployOps."))
