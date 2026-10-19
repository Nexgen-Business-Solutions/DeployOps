"""How a checklist form is described to the app: sections, fields and values (#41).

Used for the live form and for the snapshot saved on submit, so both have the same shape.
"""

import frappe
from frappe import _
from frappe.model import no_value_fields
from frappe.utils import strip_html

from deployops.checklists.form import CONDITION, FILE_COLUMNS, HEADER_FIELDS

SKIPPED = {"naming_series", "amended_from", *HEADER_FIELDS}


def _condition(expression: str | None) -> dict | None:
	match = CONDITION.match((expression or "").strip())
	return {"field": match[1], "value": match[2]} if match else None


def _options(df) -> list[str]:
	return [option for option in (df.options or "").split("\n") if option]


def _column(df) -> dict:
	return {
		"fieldname": df.fieldname,
		"fieldtype": df.fieldtype,
		"label": _(df.label),
		"options": _options(df) if df.fieldtype == "Select" else [],
		"reqd": bool(df.reqd),
		"read_only": bool(df.read_only),
	}


def _field(controller, df) -> dict:
	field = {
		"fieldname": df.fieldname,
		"fieldtype": df.fieldtype,
		"label": _(df.label or ""),
		"description": _(df.description) if df.description else None,
		"reqd": bool(df.reqd or df.mandatory_depends_on),
		"show": _condition(df.depends_on),
	}
	if df.fieldtype == "Select":
		field["options"] = _options(df)
	elif df.fieldtype == "HTML":
		field["text"] = strip_html(df.options or "").strip()
	elif df.fieldtype == "Table":
		child = frappe.get_meta(df.options)
		kind = {"DeployOps Checklist Photo": "photos", "DeployOps Checklist File": "files"}.get(df.options)
		fixed = controller.FIXED_ROWS.get(df.fieldname)
		field["table"] = {
			"kind": kind or ("grid" if fixed else "rows"),
			"columns": [_column(c) for c in child.fields if c.fieldtype not in no_value_fields],
			"file_column": FILE_COLUMNS.get(df.options),
			"min_rows": controller.MIN_ROWS.get(df.fieldname) or (1 if df.reqd else 0),
		}
	return field


def sections(doc) -> list[dict]:
	"""Sections of visible fields, in form order (Column Breaks are a Desk layout detail)."""
	sections = [{"name": "main", "label": "", "description": None, "any_of": False, "fields": []}]
	for df in doc.meta.fields:
		if df.fieldname in SKIPPED or df.hidden or df.fieldtype == "Column Break":
			continue
		if df.fieldtype == "Section Break":
			sections.append(
				{
					"name": df.fieldname,
					"label": _(df.label or ""),
					"description": _(df.description) if df.description else None,
					"any_of": df.fieldname in doc.ANY_OF,
					"show": _condition(df.depends_on),
					"fields": [],
				}
			)
			continue
		sections[-1]["fields"].append(_field(doc, df))
	return [section for section in sections if section["fields"]]


def as_text(value):
	return str(value) if value is not None and not isinstance(value, str | int | float) else value


def values(doc) -> dict:
	result = {}
	for df in doc.meta.fields:
		if df.fieldname in SKIPPED or (df.fieldtype in no_value_fields and df.fieldtype != "Table"):
			continue
		if df.fieldtype == "Table":
			columns = [c.fieldname for c in frappe.get_meta(df.options).fields]
			result[df.fieldname] = [
				{"name": row.name, **{c: as_text(row.get(c)) for c in columns}}
				for row in doc.get(df.fieldname)
			]
		else:
			result[df.fieldname] = as_text(doc.get(df.fieldname))
	return result
