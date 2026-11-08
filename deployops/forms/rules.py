"""Which forms a machine gets from the Form Rules (v2 Plan 3)."""

import frappe

from deployops.security.equipment_access import CATEGORY, get_category_items

RULE = "DeployOps Form Rule"


def categories_for_item(item_code: str) -> set[str]:
	"""The enabled equipment categories that hold `item_code`."""
	categories = frappe.get_all(CATEGORY, filters={"enabled": 1}, pluck="name")
	return {category for category in categories if item_code in get_category_items([category])}


def planned_forms(job_type: str, item_code: str) -> list[dict]:
	"""`[{"form", "required", "sort_order"}]` from the active rules for this job type and item.

	A form planned by several rules is listed once: required if any rule requires it, at the lowest
	sort order. Archived and unpublished forms are left out.
	"""
	categories = categories_for_item(item_code)
	if not categories:
		return []
	rules = frappe.get_all(
		RULE,
		filters={"job_type": job_type, "active": 1, "equipment_category": ["in", list(categories)]},
		fields=["form", "required", "sort_order"],
	)
	if not rules:
		return []
	forms = {
		form.name: form.title
		for form in frappe.get_all(
			"Form",
			filters={
				"name": ["in", list({rule.form for rule in rules})],
				"status": ["!=", "Archived"],
				"current_version": ["is", "set"],
			},
			fields=["name", "title"],
		)
	}
	planned: dict[str, dict] = {}
	for rule in rules:
		if rule.form not in forms:
			continue
		entry = planned.setdefault(
			rule.form, {"form": rule.form, "required": False, "sort_order": rule.sort_order}
		)
		entry["required"] = entry["required"] or bool(rule.required)
		entry["sort_order"] = min(entry["sort_order"], rule.sort_order)
	return sorted(planned.values(), key=lambda entry: (entry["sort_order"], forms[entry["form"]] or ""))


def plan_rows(existing: list[dict], planned: list[dict], device: str) -> list[dict]:
	"""A machine's new form rows: overrides kept, rule rows following `planned`.

	A rule row whose form is still planned keeps its `removed`, `submission` and `flagged`; one whose
	form is no longer planned is dropped. A planned form with no row gets a new rule row.
	"""
	rows = [row for row in existing if row["device"] == device]
	by_form = {row["form"]: row for row in rows if row["origin"] == "Rule"}
	result = [dict(row) for row in rows if row["origin"] == "Override"]
	overridden = {row["form"] for row in result}
	for entry in planned:
		if entry["form"] in overridden:
			continue
		current = by_form.get(entry["form"])
		new_row = (
			dict(current)
			if current
			else {
				"device": device,
				"form": entry["form"],
				"origin": "Rule",
				"removed": 0,
				"submission": None,
				"flagged": 0,
			}
		)
		new_row["required"] = int(bool(entry["required"]))
		new_row["sort_order"] = entry["sort_order"]
		result.append(new_row)
	return sorted(result, key=lambda row: (row["sort_order"], row["form"]))
