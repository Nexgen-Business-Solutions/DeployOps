"""BellaBot pre-installation checklist (#24): acceptance tests, one per requirement of the feature.

Field-by-field mapping against the original Jotform: docs/BELLABOT_PREINSTALLATION_MAPPING.md.
UAT scenarios that walk the same requirements by hand: docs/BELLABOT_PREINSTALLATION_UAT.md.
"""

from pathlib import Path

import frappe
from frappe.tests.classes.context_managers import set_user

from deployops import install
from deployops.api import checklists as checklist_api
from deployops.api import jobs as job_api
from deployops.checklists import layout, report
from deployops.patches import flag_machines_blocked_by_checklist
from deployops.tests import erpnext_fixtures as fx
from deployops.tests.test_checklists import ChecklistTestCase
from deployops.tests.test_job import JOB, make_job
from deployops.workflow import job_workflow

FORM = "DeployOps BellaBot Pre-installation"
GO, CONDITIONS, NO_GO = "GO", "GO WITH CONDITIONS", "NO GO"
OTHER_CHOICES = {"intended_use": "intended_use_other", "hazard_type": "hazard_type_other"}
OTHER_TEXTS = (
	"primary_functions_other",
	"corrective_actions_other",
	"documents_shared_other",
	"special_requirements_other",
	"unresolved_hazards_other",
)


class BellaBotTestCase(ChecklistTestCase):
	def setUp(self):
		super().setUp()
		self.job = self.working_job("Pre-installation", self.robot)
		self.set_serial(self.job, 0, "JOB-BB-1")
		self.name = self.start(self.job)
		self.row = frappe.get_doc(JOB, self.job).devices[0].name

	def set_serial(self, job, index, serial):
		with set_user(self.technician):
			doc = frappe.get_doc(JOB, job)
			doc.devices[index].serial_no = serial
			doc.save()

	def doc(self, name=None):
		return frappe.get_doc(FORM, name or self.name)

	def device(self, row=None):
		return frappe.get_doc("DeployOps Job Device", row or self.row)

	def answered(self, name=None, decision=GO, remarks=None):
		with set_user(self.technician):
			doc = self.complete(self.doc(name))
			doc.final_decision = decision
			doc.decision_remarks = remarks
			doc.save()
		return doc

	def submit(self, decision=GO, remarks="Because of the site", name=None):
		doc = self.answered(name, decision, remarks)
		with set_user(self.technician):
			doc.submit()
		return doc

	def act(self, user, action, reason=None, row=None):
		with set_user(user):
			return job_api.device_action(self.job, row or self.row, action, reason)

	def log(self):
		return frappe.get_doc(JOB, self.job).status_log[-1]


class TestSourceContent(BellaBotTestCase):
	def test_other_is_a_choice_that_needs_its_text(self):
		for field, text in OTHER_CHOICES.items():
			with self.subTest(field=field):
				doc = self.answered()
				with set_user(self.technician):
					doc.set(field, "Other")
					doc.save()
					label = frappe.get_meta(FORM).get_field(text).label
					self.assertEqual(doc.missing(), [f"{label}: required."])
					doc.set(text, "Something else")
					doc.save()
					self.assertEqual(doc.missing(), [])
					doc.set(field, frappe.get_meta(FORM).get_field(field).options.split("\n")[1])
					doc.set(text, None)
					doc.save()

	def test_tick_groups_keep_their_optional_other_text(self):
		meta = frappe.get_meta(FORM)
		for field in OTHER_TEXTS:
			with self.subTest(field=field):
				self.assertEqual(meta.get_field(field).fieldtype, "Data")
				self.assertFalse(meta.get_field(field).reqd)

	def test_no_credentials_in_the_pudu_cloud_details(self):
		meta = frappe.get_meta(FORM)
		self.assertFalse([df for df in meta.fields if "password" in df.fieldname])
		with set_user(self.technician):
			doc = self.doc()
			doc.pudu_cloud_user = "owner@example.test password: Secret1"
			with self.assertRaisesRegex(frappe.ValidationError, "do not enter passwords"):
				doc.save()

	def test_every_source_document_ships_with_the_app_in_a_real_section(self):
		sections = {df.fieldname for df in frappe.get_meta(FORM).fields if df.fieldtype == "Section Break"}
		root = Path(frappe.get_app_path("deployops", "reference_files"))
		files = {filename for filename, _title, _section in install.BELLABOT_PRE_INSTALLATION_REFERENCES}
		self.assertEqual(
			files,
			{
				"bellabot-deployment-manual.pdf",
				"bellabot-operation-guide.pdf",
				"bellabot-product-introduction.pdf",
				"bellabot-maintenance-and-care.png",
			},
		)
		for filename, _title, section in install.BELLABOT_PRE_INSTALLATION_REFERENCES:
			with self.subTest(file=filename):
				self.assertTrue((root / filename).is_file())
				self.assertIn(section, sections)


class TestDocumentsOnANewInstall(BellaBotTestCase):
	def test_seeding_from_the_app_folder_lists_them_as_private_files(self):
		settings = frappe.get_single("DeployOps Reference Files")
		settings.set("references", [])
		settings.seeded_references = None
		settings.save(ignore_permissions=True)
		install.sync_reference_files()
		rows = [
			row
			for row in frappe.get_single("DeployOps Reference Files").references
			if row.checklist == install.BELLABOT_PRE_INSTALLATION
		]
		self.assertEqual(
			[(row.title, row.section) for row in rows],
			[(title, section) for _file, title, section in install.BELLABOT_PRE_INSTALLATION_REFERENCES],
		)
		for row in rows:
			with self.subTest(title=row.title):
				self.assertTrue(frappe.db.get_value("File", {"file_url": row.file}, "is_private"))


class TestNumberRanges(BellaBotTestCase):
	"""The limits on the source form's number boxes; the 65 cm and 5° hints are guidance (mapping §4)."""

	RANGES = {  # noqa: RUF012
		"narrowest_passage_cm": 500,
		"kitchen_entrance_cm": 500,
		"max_dish_size_cm": 500,
		"two_way_corridor_cm": 500,
		"slope_degrees": 90,
	}

	def test_a_value_outside_the_source_range_stops_the_submit(self):
		meta = frappe.get_meta(FORM)
		for field, high in self.RANGES.items():
			for value in (-1, high + 1):
				with self.subTest(field=field, value=value):
					doc = self.answered()
					with set_user(self.technician):
						doc.set(field, value)
						doc.save()
						self.assertEqual(
							doc.missing(), [f"{meta.get_field(field).label}: must be between 0 and {high}."]
						)
						with self.assertRaises(frappe.ValidationError):
							doc.submit()
						doc.reload()
						doc.set(field, 10)
						doc.save()

	def test_the_limits_themselves_are_accepted(self):
		for field, high in self.RANGES.items():
			for value in (0, high):
				with self.subTest(field=field, value=value):
					doc = self.answered()
					with set_user(self.technician):
						doc.set(field, value)
						doc.save()
					self.assertEqual(doc.missing(), [])

	def test_the_guidance_hints_are_not_refusals(self):
		doc = self.answered()
		with set_user(self.technician):
			doc.update({"narrowest_passage_cm": 50, "slope_degrees": 8})
			doc.save()
		self.assertEqual(doc.missing(), [])

	def test_the_app_is_told_the_limits(self):
		fields = {f["fieldname"]: f for s in layout.sections(self.doc()) for f in s["fields"]}
		self.assertEqual(fields["slope_degrees"]["range"], {"min": 0, "max": 90})


class TestDecisionRemarks(BellaBotTestCase):
	def test_no_go_and_conditions_need_remarks(self):
		for decision in (NO_GO, CONDITIONS):
			with self.subTest(decision=decision):
				doc = self.answered(decision=decision)
				self.assertEqual(doc.missing(), ["Decision remarks: required."])
				with set_user(self.technician), self.assertRaises(frappe.ValidationError):
					doc.submit()

	def test_go_needs_no_remarks(self):
		self.assertEqual(self.answered(decision=GO).missing(), [])


class TestGo(BellaBotTestCase):
	def test_go_leaves_the_machine_free_to_complete(self):
		self.submit(GO, None)
		self.assertEqual(self.device().device_status, "Pending")
		self.act(self.technician, "start")
		self.assertEqual(self.act(self.technician, "complete"), "Completed")


class TestNoGo(BellaBotTestCase):
	def test_submitting_no_go_blocks_the_machine_with_the_remarks_as_reason(self):
		self.act(self.technician, "start")
		self.submit(NO_GO, "Passage is 50 cm")
		self.assertEqual(self.device().device_status, "Blocked")
		log = self.log()
		self.assertEqual(
			(log.action, log.from_status, log.to_status, log.user),
			("machine: block", "In Progress", "Blocked", self.technician),
		)
		self.assertIn("Passage is 50 cm", log.reason)
		self.assertIn(NO_GO, log.reason)

	def test_a_machine_not_yet_started_is_blocked_too(self):
		self.submit(NO_GO)
		self.assertEqual(self.device().device_status, "Blocked")

	def test_the_job_cannot_go_to_review(self):
		self.submit(NO_GO)
		with set_user(self.technician), self.assertRaisesRegex(frappe.ValidationError, "is blocked"):
			job_api.job_action(self.job, "submit")

	def test_the_technician_cannot_clear_it(self):
		self.submit(NO_GO)
		with self.assertRaises(frappe.PermissionError):
			self.act(self.technician, "unblock", "I fixed it")
		self.assertEqual(self.device().device_status, "Blocked")

	def test_clearing_needs_a_reason_and_is_logged(self):
		self.submit(NO_GO)
		for user in (self.supervisor, self.manager):
			with self.subTest(user=user):
				with self.assertRaisesRegex(frappe.ValidationError, "reason is required"):
					self.act(user, "unblock")
		self.assertEqual(self.act(self.supervisor, "unblock", "Customer widened the passage"), "In Progress")
		log = self.log()
		self.assertEqual((log.action, log.user), ("machine: unblock", self.supervisor))
		self.assertEqual(log.reason, "Customer widened the passage")
		self.assertEqual(self.act(self.technician, "complete"), "Completed")

	def test_the_manager_can_clear_it_as_well(self):
		self.submit(NO_GO)
		self.assertEqual(self.act(self.manager, "unblock", "Accepted the risk"), "In Progress")

	def test_the_app_is_told_the_reason_is_needed(self):
		self.submit(NO_GO)
		with set_user(self.supervisor):
			actions = job_workflow.get_device_actions(frappe.get_doc(JOB, self.job))[self.row]
		self.assertTrue(next(a for a in actions if a["action"] == "unblock")["reason_required"])

	def test_a_machine_blocked_by_hand_still_unblocks_without_a_reason(self):
		self.act(self.technician, "block", "Door locked")
		self.assertEqual(self.act(self.supervisor, "unblock"), "In Progress")

	def test_out_of_scope_supervisor_cannot_clear_it(self):
		self.submit(NO_GO)
		profile = frappe.get_doc("DeployOps Equipment Access Profile", {"user": self.supervisor})
		profile.categories = [row for row in profile.categories if row.category != "_Test Robot"]
		profile.save(ignore_permissions=True)
		with self.assertRaises(frappe.PermissionError):
			self.act(self.supervisor, "unblock", "Not my equipment")


class TestGoWithConditions(BellaBotTestCase):
	def test_the_machine_stays_workable_and_the_conditions_are_logged(self):
		self.act(self.technician, "start")
		self.submit(CONDITIONS, "Remove the loose cables first")
		self.assertEqual(self.device().device_status, "In Progress")
		self.assertIn("Remove the loose cables first", self.log().reason)

	def test_complete_is_refused_until_approved(self):
		self.act(self.technician, "start")
		self.submit(CONDITIONS)
		with self.assertRaisesRegex(frappe.ValidationError, "conditions"):
			self.act(self.technician, "complete")
		with set_user(self.technician), self.assertRaises(frappe.ValidationError):
			job_api.job_action(self.job, "submit")

	def test_approval_records_who_and_when_then_the_machine_completes(self):
		self.act(self.technician, "start")
		self.submit(CONDITIONS)
		self.assertEqual(self.act(self.supervisor, "approve_conditions"), "In Progress")
		device = self.device()
		self.assertEqual(device.conditions_approved_by, self.supervisor)
		self.assertTrue(device.conditions_approved_on)
		log = self.log()
		self.assertEqual(
			(log.action, log.user, log.from_status, log.to_status),
			("machine: approve_conditions", self.supervisor, "In Progress", "In Progress"),
		)
		self.assertEqual(self.act(self.technician, "complete"), "Completed")
		with set_user(self.technician):
			self.assertEqual(job_api.job_action(self.job, "submit"), "Pending Review")

	def test_a_machine_not_yet_started_can_be_approved(self):
		self.submit(CONDITIONS)
		self.assertEqual(self.act(self.manager, "approve_conditions"), "Pending")
		self.assertEqual(self.device().conditions_approved_by, self.manager)

	def test_the_technician_cannot_approve(self):
		self.submit(CONDITIONS)
		with self.assertRaises(frappe.PermissionError):
			self.act(self.technician, "approve_conditions")
		self.assertFalse(self.device().conditions_approved_by)

	def test_out_of_scope_supervisor_cannot_approve(self):
		self.submit(CONDITIONS)
		profile = frappe.get_doc("DeployOps Equipment Access Profile", {"user": self.supervisor})
		profile.categories = [row for row in profile.categories if row.category != "_Test Robot"]
		profile.save(ignore_permissions=True)
		with self.assertRaises(frappe.PermissionError):
			self.act(self.supervisor, "approve_conditions")

	def test_the_action_exists_only_while_approval_is_waiting(self):
		def offered():
			with set_user(self.supervisor):
				actions = job_workflow.get_device_actions(frappe.get_doc(JOB, self.job))[self.row]
			return "approve_conditions" in [a["action"] for a in actions]

		self.assertFalse(offered())  # no decision yet
		with self.assertRaisesRegex(frappe.ValidationError, "no conditions"):
			self.act(self.supervisor, "approve_conditions")
		self.submit(CONDITIONS)
		self.assertTrue(offered())
		self.act(self.supervisor, "approve_conditions")
		self.assertFalse(offered())
		with self.assertRaisesRegex(frappe.ValidationError, "no conditions"):
			self.act(self.manager, "approve_conditions")  # not a second time

	def test_the_approval_cannot_be_written_directly(self):
		self.submit(CONDITIONS)
		with set_user(self.supervisor), self.assertRaisesRegex(frappe.ValidationError, "job workflow"):
			job = frappe.get_doc(JOB, self.job)
			job.devices[0].conditions_approved_by = self.supervisor
			job.save()

	def test_a_new_form_needs_a_new_approval(self):
		self.submit(CONDITIONS)
		self.act(self.supervisor, "approve_conditions")
		with set_user(self.manager):
			checklist_api.cancel_checklist(FORM, self.name, "Survey repeated")
		with set_user(self.technician):
			new = checklist_api.start_checklist(self.job, self.row)["name"]
		self.submit(CONDITIONS, "New conditions", name=new)
		self.assertFalse(self.device().conditions_approved_by)
		self.act(self.technician, "start")
		with self.assertRaisesRegex(frappe.ValidationError, "conditions"):
			self.act(self.technician, "complete")


class TestReplacementForm(BellaBotTestCase):
	"""A Manager cancels a submitted form on a machine that was already completed, and a new one follows."""

	def replacement_after_completing(self):
		self.submit(GO, None)
		self.act(self.technician, "start")
		self.act(self.technician, "complete")
		with set_user(self.manager):
			checklist_api.cancel_checklist(FORM, self.name, "Survey repeated")
		with set_user(self.technician):
			return checklist_api.start_checklist(self.job, self.row)["name"]

	def test_no_go_blocks_a_completed_machine(self):
		new = self.replacement_after_completing()
		self.submit(NO_GO, "The route changed", name=new)
		self.assertEqual(self.device().device_status, "Blocked")
		log = self.log()
		self.assertEqual((log.from_status, log.to_status), ("Completed", "Blocked"))

	def test_conditions_reopen_a_completed_machine_until_approved(self):
		new = self.replacement_after_completing()
		self.submit(CONDITIONS, "Remove the loose cables first", name=new)
		self.assertEqual(self.device().device_status, "In Progress")
		log = self.log()
		self.assertEqual((log.from_status, log.to_status), ("Completed", "In Progress"))
		with self.assertRaisesRegex(frappe.ValidationError, "conditions"):
			self.act(self.technician, "complete")
		self.act(self.supervisor, "approve_conditions")
		self.assertEqual(self.act(self.technician, "complete"), "Completed")

	def test_cancelling_a_no_go_form_leaves_the_machine_blocked(self):
		self.submit(NO_GO)
		with set_user(self.manager):
			checklist_api.cancel_checklist(FORM, self.name, "Survey repeated")
		self.assertEqual(self.device().device_status, "Blocked")

	def cancelled_no_go(self):
		self.submit(NO_GO)
		with set_user(self.manager):
			checklist_api.cancel_checklist(FORM, self.name, "Survey repeated")

	def assert_clearing_needs_a_reason(self):
		job = frappe.get_doc(JOB, self.job)
		with set_user(self.supervisor):
			unblock = next(
				a for a in job_workflow.get_device_actions(job)[self.row] if a["action"] == "unblock"
			)
		self.assertTrue(unblock["reason_required"])
		with self.assertRaisesRegex(frappe.ValidationError, "reason is required"):
			self.act(self.supervisor, "unblock")
		self.assertEqual(self.act(self.supervisor, "unblock", "Customer widened the passage"), "In Progress")
		self.assertEqual(self.log().reason, "Customer widened the passage")

	def test_clearing_after_cancelling_with_no_replacement_needs_a_reason(self):
		self.cancelled_no_go()
		self.assert_clearing_needs_a_reason()

	def test_clearing_with_a_replacement_draft_needs_a_reason(self):
		self.cancelled_no_go()
		with set_user(self.technician):
			checklist_api.start_checklist(self.job, self.row)
		self.assert_clearing_needs_a_reason()

	def test_clearing_after_a_go_replacement_needs_a_reason(self):
		self.cancelled_no_go()
		with set_user(self.technician):
			new = checklist_api.start_checklist(self.job, self.row)["name"]
		self.submit(GO, None, name=new)
		self.assertEqual(self.device().device_status, "Blocked")
		self.assert_clearing_needs_a_reason()


class TestBlockedFlagPatch(BellaBotTestCase):
	"""Machines blocked by a NO GO before #25 have no flag; the patch sets it so clearing needs a reason."""

	def run_patch_without_flag(self):
		frappe.db.set_value("DeployOps Job Device", self.row, "blocked_by_checklist", 0)
		flag_machines_blocked_by_checklist.execute()
		return self.device().blocked_by_checklist

	def test_a_no_go_block_gets_the_flag(self):
		self.submit(NO_GO)
		self.assertEqual(self.run_patch_without_flag(), 1)
		with self.assertRaisesRegex(frappe.ValidationError, "reason is required"):
			self.act(self.supervisor, "unblock")

	def test_a_cancelled_no_go_block_gets_the_flag(self):
		self.submit(NO_GO)
		with set_user(self.manager):
			checklist_api.cancel_checklist(FORM, self.name, "Survey repeated")
		self.assertEqual(self.run_patch_without_flag(), 1)

	def test_a_block_by_hand_does_not(self):
		self.act(self.technician, "block", "Door locked")
		self.assertEqual(self.run_patch_without_flag(), 0)

	def test_a_go_form_does_not(self):
		self.submit(GO)
		self.act(self.technician, "block", "Door locked")
		self.assertEqual(self.run_patch_without_flag(), 0)


class TestTwoMachines(ChecklistTestCase):
	def test_each_machine_has_its_own_outcome(self):
		fx.make_serial("JOB-BB-2", self.robot)
		order = fx.make_sales_order(self.customer, [self.robot, self.robot]).name
		job = make_job(
			"Sales Order", order, job_type="Pre-installation", assigned_technician=self.technician
		).name
		with set_user(self.supervisor):
			job_api.job_action(job, "start")
		with set_user(self.technician):
			doc = frappe.get_doc(JOB, job)
			doc.devices[0].serial_no = "JOB-BB-1"
			doc.devices[1].serial_no = "JOB-BB-2"
			doc.save()
			first_row, second_row = (row.name for row in doc.devices)
			first = self.complete(frappe.get_doc(FORM, checklist_api.start_checklist(job, first_row)["name"]))
			first.final_decision, first.decision_remarks = NO_GO, "Stairs on the route"
			first.save()
			first.submit()
			second = self.complete(
				frappe.get_doc(FORM, checklist_api.start_checklist(job, second_row)["name"])
			)
			second.final_decision = GO
			second.save()
			second.submit()
		statuses = {row.name: row.device_status for row in frappe.get_doc(JOB, job).devices}
		self.assertEqual((statuses[first_row], statuses[second_row]), ("Blocked", "Pending"))


class TestReport(BellaBotTestCase):
	def test_internal_and_customer_reports_show_the_decision(self):
		doc = self.submit(CONDITIONS, "Remove the loose cables first")
		self.assertIn(FORM, report.REPORTABLE)
		for audience in report.AUDIENCES:
			with self.subTest(audience=audience):
				html = report.render_html(self.doc(doc.name), audience)
				self.assertIn("Pre-installation decision", html)
				self.assertIn(CONDITIONS, html)
				self.assertIn("Remove the loose cables first", html)

	def test_desk_print_formats_render_the_same_report(self):
		doc = self.submit(GO, None)
		for print_format, kind in (
			("BellaBot Pre-installation Report", "Internal report"),
			("BellaBot Pre-installation Report (Customer)", "Customer copy"),
		):
			with self.subTest(print_format=print_format):
				self.assertIn(kind, frappe.get_print(FORM, doc.name, print_format, doc=self.doc(doc.name)))
