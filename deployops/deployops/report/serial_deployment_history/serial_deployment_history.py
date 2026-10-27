"""Serial Deployment History (#14): everything that happened to one machine."""

from frappe import _

from deployops.api.allocations import serial_history


def execute(filters=None):
	filters = filters or {}
	columns = [
		{"fieldname": "when", "label": _("When"), "fieldtype": "Datetime", "width": 170},
		{"fieldname": "source", "label": _("Recorded In"), "fieldtype": "Data", "width": 110},
		{"fieldname": "event", "label": _("Event"), "fieldtype": "Data", "width": 220},
		{
			"fieldname": "reference_doctype",
			"label": _("Document Type"),
			"fieldtype": "Link",
			"options": "DocType",
			"width": 150,
		},
		{
			"fieldname": "reference_name",
			"label": _("Document"),
			"fieldtype": "Dynamic Link",
			"options": "reference_doctype",
			"width": 190,
		},
		{"fieldname": "detail", "label": _("Detail"), "fieldtype": "Data", "width": 320},
	]
	if not filters.get("serial_no"):
		return columns, []
	return columns, serial_history(filters["serial_no"])
