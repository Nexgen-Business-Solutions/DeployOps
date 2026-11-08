import frappe
from frappe.tests.classes.context_managers import set_user

from deployops.roles import MANAGER
from deployops.tests import erpnext_fixtures as fx
from deployops.tests.forms_utils import JOB, RULE, FormJobCase, add_rule
from deployops.tests.test_forms_rules import make_category
from deployops.tests.test_job import make_job
from deployops.tests.utils import make_role_user

FORM_ROW = "DeployOps Job Device Form"


class TestMachineFormRows(FormJobCase):
	def cash_job(self, serials=("JOB-CR-1", "JOB-CR-2"), devices=None):
		note = self.delivery_note(
			[{"item_code": self.cash, "serial_and_batch_bundle": fx.make_bundle(self.cash, list(serials))}]
		)
		return make_job("Delivery Note", note, devices=devices)

	def rule(self, form: str) -> str:
		return frappe.db.get_value(RULE, {"form": form, "equipment_category": "_Test Cash"})

	def update_rule(self, form: str, **values):
		rule = frappe.get_doc(RULE, self.rule(form))
		rule.update(values)
		rule.save()

	def forms_of(self, job, device: str) -> list[tuple]:
		return [(r.form, r.required) for r in job.device_forms if r.device == device]

	def test_new_job_gets_rows_from_rules(self):
		job = self.cash_job()
		a, b = self.form_a["form"], self.form_b["form"]
		self.assertEqual(len(job.device_forms), 4)
		for device in job.devices:
			self.assertEqual(self.forms_of(job, device.name), [(a, 1), (b, 0)])
		self.assertTrue(all(r.origin == "Rule" and not r.removed for r in job.device_forms))
		self.assertEqual(job.device_forms[0].form_title, "Job form job-form-a")
		saved = frappe.get_all(FORM_ROW, filters={"parent": job.name, "parenttype": JOB})
		self.assertEqual(len(saved), 4)

	def test_several_forms_per_machine_ordered(self):
		frappe.db.set_value(RULE, self.rule(self.form_a["form"]), "sort_order", 2)
		frappe.db.set_value(RULE, self.rule(self.form_b["form"]), "sort_order", 1)
		job = self.cash_job()
		device = job.devices[0].name
		self.assertEqual(self.forms_of(job, device), [(self.form_b["form"], 0), (self.form_a["form"], 1)])

	def test_caller_rows_ignored_on_new_job(self):
		note = self.delivery_note(
			[{"item_code": self.cash, "serial_and_batch_bundle": fx.make_bundle(self.cash, ["JOB-CR-1"])}]
		)
		job = frappe.get_doc(
			{
				"doctype": JOB,
				"job_type": "Installation",
				"company": fx.COMPANY,
				"source_doctype": "Delivery Note",
				"source_name": note,
				"device_forms": [
					{"device": "nothing", "form": self.form_b["form"], "required": 1, "origin": "Override"}
				],
			}
		).insert()
		device = job.devices[0].name
		self.assertEqual(self.forms_of(job, device), [(self.form_a["form"], 1), (self.form_b["form"], 0)])
		self.assertEqual({r.device for r in job.device_forms}, {device})

	def test_rows_cannot_be_edited_directly(self):
		job = self.cash_job()
		job.device_forms[1].required = 1
		with self.assertRaisesRegex(frappe.ValidationError, "set by form rules and overrides"):
			job.save()

		job.reload()
		job.append(
			"device_forms",
			{"device": job.devices[0].name, "form": self.form_b["form"], "origin": "Override"},
		)
		with self.assertRaisesRegex(frappe.ValidationError, "set by form rules and overrides"):
			job.save()

	def test_rows_follow_rules_until_first_form_started(self):
		a, b = self.form_a["form"], self.form_b["form"]
		job = self.cash_job()
		first, second = (d.name for d in job.devices)

		self.update_rule(b, required=1)
		job.reload()
		self.assertEqual(self.forms_of(job, first), [(a, 1), (b, 1)])
		self.assertEqual(self.forms_of(job, second), [(a, 1), (b, 1)])

		with set_user("Administrator"):
			submission = frappe.get_doc(
				{
					"doctype": "Form Submission",
					"form": a,
					"form_version": frappe.db.get_value("Form", a, "current_version"),
					"context_doctype": JOB,
					"context_name": job.name,
					"context_row": first,
				}
			)
			submission.flags.forms_core_start = True
			submission.insert(ignore_permissions=True)

		self.update_rule(a, active=0)
		job.reload()
		self.assertEqual(self.forms_of(job, first), [(a, 1), (b, 1)])
		self.assertEqual(self.forms_of(job, second), [(b, 1)])

	def test_deleted_rule_removes_its_rows(self):
		job = self.cash_job()
		frappe.delete_doc(RULE, self.rule(self.form_b["form"]), ignore_permissions=True)
		job.reload()
		for device in job.devices:
			self.assertEqual(self.forms_of(job, device.name), [(self.form_a["form"], 1)])

	def test_added_machine_gets_rows_removed_machine_loses_them(self):
		job = self.cash_job(devices=[{"item_code": self.cash, "serial_no": "JOB-CR-1"}])
		self.assertEqual(job.status, "Draft")
		self.assertEqual(len(job.device_forms), 2)

		job.append("devices", {"item_code": self.cash, "serial_no": "JOB-CR-2"})
		job.save()
		first, second = (d.name for d in job.devices)
		self.assertEqual(len(self.forms_of(job, second)), 2)

		job.set("devices", [d for d in job.devices if d.name != first])
		job.save()
		self.assertEqual({r.device for r in job.device_forms}, {second})
		self.assertFalse(frappe.db.exists(FORM_ROW, {"parent": job.name, "device": first}))

	def test_completed_and_cancelled_machines_not_resynced(self):
		a, b = self.form_a["form"], self.form_b["form"]
		job = self.cash_job(serials=("JOB-CR-1", "JOB-CR-2", "JOB-CR-3"))
		completed, cancelled, pending = (d.name for d in job.devices)
		frappe.db.set_value("DeployOps Job Device", completed, "device_status", "Completed")
		frappe.db.set_value("DeployOps Job Device", cancelled, "device_status", "Cancelled")

		self.update_rule(b, required=1)
		job.reload()
		self.assertEqual(self.forms_of(job, completed), [(a, 1), (b, 0)])
		self.assertEqual(self.forms_of(job, cancelled), [(a, 1), (b, 0)])
		self.assertEqual(self.forms_of(job, pending), [(a, 1), (b, 1)])

	def test_rule_change_resyncs_jobs_outside_editor_scope(self):
		make_category("_Test Robot", [self.robot])
		add_rule("Installation", "_Test Robot", self.form_a["form"])
		job = make_job("Delivery Note", self.delivery_note())
		robot = next(d.name for d in job.devices if d.item_code == self.robot)
		cash = next(d.name for d in job.devices if d.item_code == self.cash)

		manager = make_role_user(MANAGER)
		frappe.db.delete("DeployOps Equipment Access Profile Category", {"parent": manager})
		frappe.db.delete("DeployOps Equipment Access Profile", {"name": manager})
		frappe.get_doc(
			{
				"doctype": "DeployOps Equipment Access Profile",
				"user": manager,
				"categories": [{"category": "_Test Cash"}],
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.cache.hdel, "user_permissions", manager)

		with set_user(manager):
			self.update_rule(self.form_b["form"], required=1)
		job.reload()
		self.assertEqual(self.forms_of(job, cash), [(self.form_a["form"], 1), (self.form_b["form"], 1)])
		self.assertEqual(self.forms_of(job, robot), [(self.form_a["form"], 1)])
