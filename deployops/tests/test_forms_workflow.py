"""v2 Plan 3 Task 4: form outcomes, required forms, machine changes and v1 coexistence."""

import frappe
from forms_core import api
from frappe.tests.classes.context_managers import set_user

from deployops.api import checklists as checklist_api
from deployops.api import jobs as job_api
from deployops.api import technician as technician_api
from deployops.checklists.cards import form_for_device
from deployops.forms import machine_forms
from deployops.roles import MANAGER
from deployops.tests import erpnext_fixtures as fx
from deployops.tests.forms_utils import JOB, RULE, FormJobCase, add_rule, publish_job_form
from deployops.tests.test_forms_provider import make_user
from deployops.tests.test_forms_rules import make_category
from deployops.tests.test_job import make_job
from deployops.tests.utils import make_role_user

DEVICE = "DeployOps Job Device"
FORM_ROW = "DeployOps Job Device Form"
SUBMISSION = "Form Submission"
CATEGORY = "DeployOps Equipment Category"
TITLE_A = "Job form job-form-a"
TITLE_B = "Job form job-form-b"


class TestFormsWorkflow(FormJobCase):
	def setUp(self):
		super().setUp()
		self.manager = make_user(make_role_user(MANAGER), MANAGER)
		self.addCleanup(frappe.flags.pop, "deployops_form_cancel", None)

	# -- helpers ------------------------------------------------------------------------------

	def working_job(self, devices=None, serials=("JOB-CR-1",), rows=None) -> str:
		"""An Installation job On Site with its first machine In Progress."""
		rows = rows or [
			{"item_code": self.cash, "serial_and_batch_bundle": fx.make_bundle(self.cash, list(serials))}
		]
		note = self.delivery_note(rows)
		job = make_job("Delivery Note", note, devices=devices, assigned_technician=self.technician).name
		with set_user(self.supervisor):
			job_api.job_action(job, "start")
		with set_user(self.technician):
			job_api.job_action(job, "arrive")
			job_api.device_action(job, self.device_of(job), "start")
		return job

	def device_of(self, job: str) -> str:
		return frappe.get_doc(JOB, job).devices[0].name

	def start(self, job: str, form: dict) -> str:
		with set_user(self.technician):
			return api.start_submission(form["form"], JOB, job, self.device_of(job))

	def fill(self, name: str, form: dict, safe: str = "Yes", submit: bool = True):
		with set_user(self.technician):
			api.save_answers(name, {form["note"]: "Fitted", form["safe"]: safe})
			if submit:
				api.submit(name)

	def complete(self, job: str):
		with set_user(self.technician):
			return job_api.device_action(job, self.device_of(job), "complete")

	def cancel_form(self, name: str, reason: str):
		"""Cancel as the Manager, the way Task 5's cancel_machine_form will."""
		frappe.flags.deployops_form_cancel = reason
		with set_user(self.manager):
			doc = frappe.get_doc(SUBMISSION, name)
			self.assertTrue(doc.has_permission("cancel"))
			doc.flags.ignore_permissions = True  # Frappe's cancel also checks write, final once submitted
			doc.cancel()
		frappe.flags.pop("deployops_form_cancel", None)

	def device(self, job: str):
		return frappe.get_doc(JOB, job).devices[0]

	def log(self, job: str) -> list[tuple]:
		return [(r.action, r.reason) for r in frappe.get_doc(JOB, job).status_log]

	def form_row(self, job: str, form: dict):
		return next(r for r in frappe.get_doc(JOB, job).device_forms if r.form == form["form"])

	def use_v1_cards(self):
		frappe.db.set_value(CATEGORY, {"name": ["is", "set"]}, "product_line", None)
		frappe.db.set_value(CATEGORY, "_Test Cash", "product_line", "Cashmatic")

	# -- required forms -------------------------------------------------------------------------

	def test_machine_cannot_complete_until_required_forms_submitted(self):
		job = self.working_job()
		with self.assertRaisesRegex(
			frappe.ValidationError, f"Submit the required form {TITLE_A} of machine .* before completing it"
		):
			self.complete(job)
		self.assertEqual(self.device(job).device_status, "In Progress")

		self.start(job, self.form_b)  # the optional form stays a draft
		self.fill(self.start(job, self.form_a), self.form_a)
		self.assertEqual(self.complete(job), "Completed")
		job_doc = frappe.get_doc(JOB, job)
		statuses = {r.form: machine_forms.row_status(r) for r in job_doc.device_forms}
		self.assertEqual(statuses, {self.form_a["form"]: "Submitted", self.form_b["form"]: "Draft"})
		self.assertEqual(machine_forms.missing_required(job_doc, self.device_of(job)), [])

	def test_job_cannot_be_submitted_with_missing_required_form(self):
		job = self.working_job()
		frappe.db.set_value(DEVICE, self.device_of(job), "device_status", "Completed")
		with (
			set_user(self.technician),
			self.assertRaisesRegex(frappe.ValidationError, f"the required form {TITLE_A} of machine"),
		):
			job_api.job_action(job, "submit")

		self.fill(self.start(job, self.form_a), self.form_a)
		with set_user(self.technician):
			self.assertEqual(job_api.job_action(job, "submit"), "Pending Review")

	# -- outcomes -------------------------------------------------------------------------------

	def test_block_outcome_blocks_machine_and_unblock_needs_reason(self):
		block = publish_job_form("job-form-block", outcome="block_machine")
		add_rule("Installation", "_Test Cash", block["form"], required=False, sort_order=2)
		job = self.working_job()
		name = self.start(job, block)
		self.fill(name, block, safe="No")

		device = self.device(job)
		self.assertEqual(device.device_status, "Blocked")
		self.assertTrue(device.blocked_by_checklist)
		self.assertIn(("machine: block", "Job form job-form-block: Safe"), self.log(job))
		self.assertFalse(self.form_row(job, block).flagged)

		with set_user(self.supervisor):
			with self.assertRaisesRegex(frappe.ValidationError, "A reason is required"):
				job_api.device_action(job, device.name, "unblock")
			self.assertEqual(
				job_api.device_action(job, device.name, "unblock", "Checked on site"), "In Progress"
			)
		self.assertFalse(self.device(job).blocked_by_checklist)

	def test_safe_answer_triggers_no_outcome(self):
		block = publish_job_form("job-form-block", outcome="block_machine")
		add_rule("Installation", "_Test Cash", block["form"], required=False, sort_order=2)
		job = self.working_job()
		self.fill(self.start(job, block), block, safe="Yes")
		self.assertEqual(self.device(job).device_status, "In Progress")
		self.assertNotIn("machine: block", [action for action, _reason in self.log(job)])

	def test_flag_outcome_flags_row_without_blocking(self):
		flag = publish_job_form("job-form-flag", outcome="flag_for_review")
		add_rule("Installation", "_Test Cash", flag["form"], required=False, sort_order=2)
		job = self.working_job()
		self.fill(self.start(job, flag), flag, safe="No")

		self.assertEqual(self.device(job).device_status, "In Progress")
		self.assertFalse(self.device(job).blocked_by_checklist)
		self.assertTrue(self.form_row(job, flag).flagged)
		self.assertIn(("machine: flagged for review", "Job form job-form-flag: Safe"), self.log(job))

	# -- cancel ---------------------------------------------------------------------------------

	def test_cancel_required_on_completed_machine_reopens_it(self):
		job = self.working_job()
		name = self.start(job, self.form_a)
		self.fill(name, self.form_a)
		self.complete(job)
		with set_user(self.technician):
			job_api.job_action(job, "submit")

		self.cancel_form(name, "Wrong serial photographed")
		self.assertEqual(frappe.db.get_value(SUBMISSION, name, "docstatus"), 2)
		self.assertEqual(self.device(job).device_status, "In Progress")
		log = self.log(job)
		self.assertIn(("form: cancelled", f"{TITLE_A}: Wrong serial photographed"), log)
		self.assertIn(("machine: reopened", TITLE_A), log)
		self.assertEqual(machine_forms.row_status(self.form_row(job, self.form_a)), "Not started")
		with (
			set_user(self.supervisor),
			self.assertRaisesRegex(frappe.ValidationError, "is not completed"),
		):
			job_api.job_action(job, "approve")

	def test_frappe_cancel_also_checks_write(self):
		"""Write is final on a submitted form, so even a permitted cancel must skip Frappe's own check."""
		job = self.working_job()
		name = self.start(job, self.form_a)
		self.fill(name, self.form_a)
		frappe.flags.deployops_form_cancel = "Wrong form"
		with set_user(self.manager):
			doc = frappe.get_doc(SUBMISSION, name)
			self.assertTrue(doc.has_permission("cancel"))
			with self.assertRaises(frappe.PermissionError):
				doc.cancel()
		self.assertEqual(frappe.db.get_value(SUBMISSION, name, "docstatus"), 1)

	def test_cancel_optional_form_keeps_machine_completed(self):
		job = self.working_job()
		self.fill(self.start(job, self.form_a), self.form_a)
		optional = self.start(job, self.form_b)
		self.fill(optional, self.form_b)
		self.complete(job)
		self.cancel_form(optional, "Duplicate")
		self.assertEqual(self.device(job).device_status, "Completed")
		self.assertNotIn("machine: reopened", [action for action, _reason in self.log(job)])

	def test_cancel_keeps_block_and_clears_flag(self):
		flag = publish_job_form("job-form-flag", outcome=("block_machine", "flag_for_review"))
		add_rule("Installation", "_Test Cash", flag["form"], required=False, sort_order=2)
		job = self.working_job()
		name = self.start(job, flag)
		self.fill(name, flag, safe="No")
		self.assertTrue(self.form_row(job, flag).flagged)
		self.assertEqual(self.device(job).device_status, "Blocked")

		self.cancel_form(name, "Retake")
		self.assertFalse(self.form_row(job, flag).flagged)
		self.assertEqual(self.device(job).device_status, "Blocked")
		self.assertTrue(self.device(job).blocked_by_checklist)

	def test_cancelled_machine_draft_cannot_be_submitted(self):
		job = self.working_job()
		name = self.start(job, self.form_a)
		self.fill(name, self.form_a, submit=False)
		with set_user(self.supervisor):
			job_api.device_action(job, self.device_of(job), "cancel", "Not delivered")
		with set_user(self.technician), self.assertRaises(frappe.PermissionError):
			api.submit(name)
		self.assertEqual(frappe.db.get_value(SUBMISSION, name, "docstatus"), 0)

	def test_draft_on_removed_row_cannot_be_submitted(self):
		job = self.working_job()
		name = self.start(job, self.form_a)
		self.fill(name, self.form_a, submit=False)
		frappe.db.set_value(FORM_ROW, {"parent": job, "form": self.form_a["form"]}, "removed", 1)
		with set_user(self.technician), self.assertRaises(frappe.PermissionError):
			api.submit(name)
		self.assertEqual(frappe.db.get_value(SUBMISSION, name, "docstatus"), 0)

	# -- machine changes ------------------------------------------------------------------------

	def test_serial_swap_draft_follows_submitted_keeps(self):
		job = self.working_job(
			devices=[{"item_code": self.cash, "serial_no": "JOB-CR-1"}], serials=("JOB-CR-1", "JOB-CR-2")
		)
		submitted = self.start(job, self.form_a)
		self.fill(submitted, self.form_a)
		draft = self.start(job, self.form_b)

		job_doc = frappe.get_doc(JOB, job)
		job_doc.devices[0].serial_no = "JOB-CR-2"
		job_doc.save()

		with set_user(self.technician):
			self.assertEqual(api.save_answers(draft, {})[self.form_b["serial"]], "JOB-CR-2")
			self.assertEqual(api.get_submission(submitted)["answers"][self.form_a["serial"]], "JOB-CR-1")

	def test_item_change_refused_with_live_form(self):
		rows = [
			{"item_code": self.cash, "serial_and_batch_bundle": fx.make_bundle(self.cash, ["JOB-CR-1"])},
			{"item_code": self.vp22, "serial_and_batch_bundle": fx.make_bundle(self.vp22, ["JOB-VP-1"])},
		]
		job = self.working_job(devices=[{"item_code": self.cash, "serial_no": "JOB-CR-1"}], rows=rows)
		self.start(job, self.form_a)
		job_doc = frappe.get_doc(JOB, job)
		job_doc.devices[0].item_code, job_doc.devices[0].serial_no = self.vp22, "JOB-VP-1"
		with self.assertRaisesRegex(
			frappe.ValidationError,
			"Row #1: this machine has forms; a manager must cancel or discard them before the machine can be changed.",
		):
			job_doc.save()
		self.assertTrue(machine_forms.has_live_submission(job, self.device_of(job)))

	def test_item_change_after_cancel_replans_rows(self):
		make_category("_Test Robots", [self.robot])
		robot_form = publish_job_form("job-form-robot")
		add_rule("Installation", "_Test Robots", robot_form["form"])
		make_user(self.technician, "DeployOps Technician", categories=("_Test Cash", "_Test Robots"))
		rows = [
			{"item_code": self.cash, "serial_and_batch_bundle": fx.make_bundle(self.cash, ["JOB-CR-1"])},
			{"item_code": self.robot, "serial_no": "JOB-BB-1"},
		]
		job = self.working_job(devices=[{"item_code": self.cash, "serial_no": "JOB-CR-1"}], rows=rows)
		name = self.start(job, self.form_a)
		self.fill(name, self.form_a)
		self.cancel_form(name, "Wrong machine")
		self.assertFalse(machine_forms.has_live_submission(job, self.device_of(job)))

		job_doc = frappe.get_doc(JOB, job)
		job_doc.devices[0].item_code, job_doc.devices[0].serial_no = self.robot, "JOB-BB-1"
		job_doc.save()

		job_doc.reload()
		self.assertEqual([(r.form, r.required) for r in job_doc.device_forms], [(robot_form["form"], 1)])
		self.assertEqual(
			machine_forms.missing_required(job_doc, self.device_of(job)), ["Job form job-form-robot"]
		)
		started = self.start(job, robot_form)
		self.assertEqual(frappe.db.get_value(SUBMISSION, started, "context_row"), self.device_of(job))
		self.assertEqual(self.form_row(job, robot_form).submission, started)

	def test_block_on_blocked_machine_logs_once(self):
		block = publish_job_form("job-form-block", outcome="block_machine")
		add_rule("Installation", "_Test Cash", block["form"], required=False, sort_order=2)
		job = self.working_job()
		with set_user(self.technician):
			job_api.device_action(job, self.device_of(job), "block", "Wall not ready")
		self.assertFalse(self.device(job).blocked_by_checklist)
		self.fill(self.start(job, block), block, safe="No")
		self.assertTrue(self.device(job).blocked_by_checklist)
		blocks = [action for action, _reason in self.log(job) if action == "machine: block"]
		self.assertEqual(len(blocks), 1)  # the manual block only

	# -- v1 coexistence -------------------------------------------------------------------------

	def test_v1_checklist_machine_gets_no_rows(self):
		self.use_v1_cards()
		visit = fx.make_maintenance_visit(self.customer, [{"item_code": self.cash, "serial_no": "JOB-CR-1"}])
		job = make_job(
			"Maintenance Visit", visit.name, job_type="Maintenance", assigned_technician=self.technician
		).name
		with set_user(self.supervisor):
			job_api.job_action(job, "start")
		device = self.device_of(job)
		with set_user(self.technician):
			checklist_api.start_checklist(job, device)
			job_api.device_action(job, device, "start")

		add_rule("Maintenance", "_Test Cash", self.form_a["form"])
		machine_forms.resync_job_type("Maintenance")
		job_doc = frappe.get_doc(JOB, job)
		self.assertEqual(job_doc.device_forms, [])
		self.assertFalse(machine_forms.uses_forms(job_doc, device))
		with self.assertRaisesRegex(frappe.ValidationError, "Submit the checklist of machine"):
			self.complete(job)

	def test_v1_start_refused_when_machine_uses_forms(self):
		self.use_v1_cards()
		job = self.working_job()
		device = self.device_of(job)
		self.assertIsNone(form_for_device(job, device))  # the job start skipped it
		with (
			set_user(self.technician),
			self.assertRaisesRegex(frappe.ValidationError, "This machine uses forms from the form builder."),
		):
			checklist_api.start_checklist(job, device)
		with set_user(self.technician):
			machine = technician_api.job_view(job)["machines"][0]
		self.assertTrue(machine["uses_forms"])
		self.assertFalse(machine["can_start_checklist"])

	def test_v1_machines_unchanged(self):
		self.use_v1_cards()
		frappe.db.delete(RULE)
		job = self.working_job()
		device = self.device_of(job)
		job_doc = frappe.get_doc(JOB, job)
		self.assertEqual(job_doc.device_forms, [])
		self.assertIsNotNone(form_for_device(job, device))  # created on job start
		with self.assertRaisesRegex(frappe.ValidationError, "Submit the checklist of machine"):
			self.complete(job)
		with set_user(self.technician):
			machine = technician_api.job_view(job)["machines"][0]
		self.assertFalse(machine["uses_forms"])
		self.assertIsNotNone(machine["checklist"])
