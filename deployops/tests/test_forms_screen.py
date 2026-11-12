"""Demo seed coverage for the standalone v2 technician screen."""

import json

import frappe
from forms_core import api, field_types
from frappe.tests.classes.context_managers import set_user

from deployops.tests.forms_utils import JOB, FormJobCase


class TestFormsDemo(FormJobCase):
	def test_demo_seed(self):
		from deployops.tests.forms_demo import seed

		result = seed(self.technician)
		form = frappe.get_doc("Form", result["form"])
		definition = json.loads(frappe.db.get_value("Form Version", form.current_version, "definition"))
		self.assertEqual(
			{f["type"] for s in definition["sections"] for f in s["fields"]},
			set(field_types.all_types()),
		)
		job = frappe.get_doc(JOB, result["job"])
		rows = [r for r in job.device_forms if r.form == form.name and not r.removed and r.required]
		self.assertEqual(len(rows), 2)
		self.assertEqual({r.device for r in rows}, set(result["rows"]))
		with set_user(self.technician):
			view = api.get_submission(result["submission"])
			self.assertEqual(view["answers"]["f_demo01"], "DEMO-SN-1")
			self.assertTrue(view["can_write"])
		version_count = frappe.db.count("Form Version", {"form": form.name})
		again = seed(self.technician)
		self.assertEqual(
			(again["form"], again["job"], again["submission"]),
			(result["form"], result["job"], result["submission"]),
		)
		self.assertEqual(frappe.db.count("Form Version", {"form": form.name}), version_count)
