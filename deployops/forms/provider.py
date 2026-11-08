"""The forms_core context provider for DeployOps jobs (v2 Plan 3, spec §7.1)."""

from typing import Any

import frappe
from forms_core.context import ContextProvider
from frappe import _

JOB = "DeployOps Job"
DEVICE = "DeployOps Job Device"

# Values a job form can fill from, as (value, label, forms_core field type).
VALUES = (
	("job", "Job", "text"),
	("job_type", "Job type", "text"),
	("customer", "Customer", "text"),
	("customer_name", "Customer name", "text"),
	("address", "Address", "long_text"),
	("contact", "Contact", "long_text"),
	("company", "Company", "text"),
	("planned_date", "Planned date", "date"),
	("technician", "Technician", "text"),
	("technician_user", "Technician user", "text"),
	("item_code", "Item code", "text"),
	("item_name", "Item name", "text"),
	("serial_no", "Serial no", "text"),
)


class JobFormProvider(ContextProvider):
	def values(self, context_name: str, context_row: str | None) -> dict[str, Any]:
		job = (
			frappe.db.get_value(
				JOB,
				context_name,
				[
					"name",
					"job_type",
					"customer",
					"customer_name",
					"address_display",
					"contact_display",
					"company",
					"planned_date",
					"assigned_technician",
				],
				as_dict=True,
			)
			or frappe._dict()
		)
		device = None
		if context_row:
			device = frappe.db.get_value(
				DEVICE,
				{"name": context_row, "parent": context_name, "parenttype": JOB},
				["item_code", "item_name", "serial_no"],
				as_dict=True,
			)
		device = device or frappe._dict()
		technician = job.assigned_technician
		return {
			"job": job.name,
			"job_type": job.job_type,
			"customer": job.customer,
			"customer_name": job.customer_name,
			"address": job.address_display,
			"contact": job.contact_display,
			"company": job.company,
			"planned_date": str(job.planned_date) if job.planned_date else None,
			"technician": frappe.db.get_value("User", technician, "full_name") if technician else None,
			"technician_user": technician,
			"item_code": device.item_code,
			"item_name": device.item_name,
			"serial_no": device.serial_no,
		}

	def value_catalog(self) -> list[dict]:
		return [{"value": value, "label": _(label), "type": kind} for value, label, kind in VALUES]

	def outcomes(self) -> list[dict]:
		return [
			{"effect": "block_machine", "label": _("Block the machine")},
			{"effect": "flag_for_review", "label": _("Flag for review")},
		]
