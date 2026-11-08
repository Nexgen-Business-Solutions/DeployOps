"""Helpers for the v2 form tests: job forms, Form Rules and a job test case that has both."""

import json

import frappe
from forms_core import versions
from forms_core.ids import new_id
from frappe.tests.classes.context_managers import set_user

from deployops.tests.test_job import JobTestCase

JOB = "DeployOps Job"
RULE = "DeployOps Form Rule"


def publish_job_form(key: str | None = None, outcome: str | None = None) -> dict:
	"""Publish, as Administrator, a job form with a locked serial, a required note and a yes/no."""
	key = key or "job-" + new_id("k")[2:]
	section, serial, note, safe = new_id("s"), new_id("f"), new_id("f"), new_id("f")
	safe_field = {"id": safe, "key": "safe", "type": "yes_no", "label": "Safe"}
	if outcome:
		safe_field["outcomes"] = [{"when": {"field": safe, "op": "eq", "value": "No"}, "effect": outcome}]
	definition = {
		"schema": 1,
		"sections": [
			{
				"id": section,
				"title": "Checks",
				"fields": [
					{
						"id": serial,
						"key": "serial",
						"type": "text",
						"label": "Serial",
						"fill_from": {"value": "serial_no", "locked": True},
					},
					{"id": note, "key": "note", "type": "text", "label": "Note", "required": True},
					safe_field,
				],
			}
		],
	}
	with set_user("Administrator"):
		form = frappe.get_doc(
			{
				"doctype": "Form",
				"title": f"Job form {key}",
				"key": key,
				"context_doctype": JOB,
				"draft_definition": json.dumps(definition),
			}
		).insert()
		versions.publish(form.name)
	return {"form": form.name, "serial": serial, "note": note, "safe": safe}


def add_rule(job_type: str, category: str, form: str, required: bool = True, sort_order: int = 0) -> str:
	return (
		frappe.get_doc(
			{
				"doctype": RULE,
				"job_type": job_type,
				"equipment_category": category,
				"form": form,
				"required": int(required),
				"sort_order": sort_order,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


class FormJobCase(JobTestCase):
	"""A job test case with two Installation forms on "_Test Cash": form_a required, form_b optional."""

	def setUp(self):
		super().setUp()
		self.form_a = publish_job_form("job-form-a")
		self.form_b = publish_job_form("job-form-b")
		add_rule("Installation", "_Test Cash", self.form_a["form"], required=True, sort_order=0)
		add_rule("Installation", "_Test Cash", self.form_b["form"], required=False, sort_order=1)
