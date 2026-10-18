import frappe
from frappe import _
from frappe.model.document import Document


class DeployOpsEquipmentCategory(Document):
	def validate(self):
		self.validate_unique_rows("items", "item_code", _("Item"))
		self.validate_unique_rows("item_groups", "item_group", _("Item Group"))
		self.validate_serialized_items()

	def validate_unique_rows(self, table: str, field: str, label: str):
		seen = set()
		for row in self.get(table):
			value = row.get(field)
			if value in seen:
				frappe.throw(_("Row #{0}: {1} {2} is listed more than once.").format(row.idx, label, value))
			seen.add(value)

	def validate_serialized_items(self):
		item_codes = [row.item_code for row in self.items]
		if not item_codes:
			return

		serialized = set(
			frappe.get_all("Item", filters={"name": ["in", item_codes], "has_serial_no": 1}, pluck="name")
		)
		for row in self.items:
			if row.item_code not in serialized:
				frappe.throw(
					_(
						"Row #{0}: Item {1} is not serial-numbered. Only serial-numbered equipment can be added."
					).format(row.idx, row.item_code)
				)
