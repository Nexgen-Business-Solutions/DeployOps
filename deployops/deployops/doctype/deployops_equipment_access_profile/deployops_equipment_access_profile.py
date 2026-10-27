import frappe
from frappe import _
from frappe.model.document import Document


class DeployOpsEquipmentAccessProfile(Document):
	def validate(self):
		seen = set()
		for row in self.categories:
			if row.category in seen:
				frappe.throw(
					_("Row #{0}: Category {1} is listed more than once.").format(row.idx, row.category)
				)
			seen.add(row.category)
