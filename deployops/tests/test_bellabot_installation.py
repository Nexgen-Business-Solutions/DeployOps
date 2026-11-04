"""BellaBot on-site installation checklist (#25): acceptance tests.

Source: https://form.jotform.com/262743396548066, read from the published form on 2026-11-02.
Field-by-field mapping: docs/BELLABOT_INSTALLATION_MAPPING.md. Hand-run scenarios: docs/BELLABOT_INSTALLATION_UAT.md.
"""

from pathlib import Path

import frappe
from frappe.tests.classes.context_managers import set_user
from frappe.utils import get_fullname

from deployops import install
from deployops.api import allocations as allocation_api
from deployops.api import checklists as checklist_api
from deployops.api import jobs as job_api
from deployops.checklists import layout, report
from deployops.tests import erpnext_fixtures as fx
from deployops.tests.test_checklists import ChecklistTestCase
from deployops.tests.test_job import JOB, make_job

FORM = "DeployOps BellaBot Installation"
# Section → its options in the source. At least one must be ticked, as the source requires.
AT_LEAST_ONE = {
	"localization_section": 3,
	"modes_section": 7,
	"safety_section": 5,
	"advertising_section": 3,
	"audio_section": 3,
	"training_topics_section": 10,
	"reminders_section": 2,
	"advisories_section": 5,
	"sign_off_section": 3,
}
# The source's single "Check" choice became three required ticks (CHECKLIST_ARCHITECTURE.md).
REQUIRED_TICKS = (
	"step_main_power_check_charging_docking_status",
	"step_network_connectivity_wi_fi",
	"step_pudu_link_app_installed_and_configured",
)
CHOICES = {
	"visible_damage": ["No damage", "Minor cosmetic damage", "Moderate damage", "Severe damage"],
	"delivery_status": ["Pass", "Fail", "Not Tested"],
	"cruise_status": ["Pass", "Fail", "Not Tested"],
	"recycle_status": ["Pass", "Fail", "Not Tested"],
	"birthday_status": ["Pass", "Fail", "Not Tested"],
	"safety_result": ["PASS", "FAIL"],
	"handover_confirmed": ["Yes", "No"],
}
REQUIRED = (
	"site_name",
	"installed_on",
	"deployment_type",
	"visible_damage",
	"map_name",
	"safety_result",
	"training_date",
	"handover_confirmed",
	"accepted_on",
	"customer_signatory",
	"signed_off_on",
)
# Group → the text box for its "Other" choice in the source.
OTHER_ANSWERS = {
	"localization_section": "localization_other",
	"safety_section": "safety_other",
	"advertising_section": "advertising_other",
	"audio_section": "audio_other",
	"training_topics_section": "training_topics_other",
	"reminders_section": "reminders_other",
	"advisories_section": "advisories_other",
	"sign_off_section": "sign_off_other",
}
MODE_TESTS = ("delivery_status", "cruise_status", "recycle_status", "birthday_status")
OPTIONAL = (
	"damage_note",
	"damage_corrective_action",
	"setup_notes",
	"map_notes",
	"mode_notes",
	"test_notes",
	"safety_failure_details",
	"validation_notes",
	"training_start",
	"training_end",
	"customer_remarks",
)


class BellaBotInstallationTestCase(ChecklistTestCase):
	def setUp(self):
		super().setUp()
		self.job = self.working_job("Installation", self.robot, "JOB-BB-1")
		self.name = self.start(self.job)
		self.row = frappe.get_doc(JOB, self.job).devices[0].name

	def doc(self):
		return frappe.get_doc(FORM, self.name)

	def completed(self):
		with set_user(self.technician):
			doc = self.complete(self.doc())
			doc.save()
		return doc

	def submitted(self, **answers):
		doc = self.completed()
		with set_user(self.technician):
			doc.update(answers)
			doc.save()
			doc.submit()
		return doc

	def status(self):
		return frappe.db.get_value("DeployOps Job Device", self.row, "device_status")

	def log(self):
		return frappe.get_doc(JOB, self.job).status_log[-1]

	def act(self, user, action, reason=None):
		with set_user(user):
			return job_api.device_action(self.job, self.row, action, reason)


class TestSourceContent(BellaBotInstallationTestCase):
	def test_every_source_group_has_all_its_options(self):
		for section, count in AT_LEAST_ONE.items():
			with self.subTest(section=section):
				self.assertEqual(len(self.doc().ANY_OF[section]), count)

	def test_choices_match_the_source(self):
		meta = frappe.get_meta(FORM)
		for field, options in CHOICES.items():
			with self.subTest(field=field):
				self.assertEqual(meta.get_field(field).options.split("\n")[1:], options)

	def test_a_completed_form_has_nothing_missing(self):
		self.assertEqual(self.completed().missing(), [])

	def test_each_group_needs_at_least_one_tick(self):
		meta = frappe.get_meta(FORM)
		for section, fields in self.doc().ANY_OF.items():
			with self.subTest(section=section):
				doc = self.completed()
				with set_user(self.technician):
					for field in fields:
						doc.set(field, 0)
					doc.save()
					self.assertEqual(doc.missing(), [f"{meta.get_field(section).label}: tick at least one."])
					with self.assertRaises(frappe.ValidationError):
						doc.submit()

	def test_each_power_and_network_check_must_be_ticked(self):
		meta = frappe.get_meta(FORM)
		for field in REQUIRED_TICKS:
			with self.subTest(field=field):
				doc = self.completed()
				with set_user(self.technician):
					doc.set(field, 0)
					doc.save()
					self.assertEqual(doc.missing(), [f"{meta.get_field(field).label}: not ticked."])

	def test_required_answers_stop_the_submit(self):
		meta = frappe.get_meta(FORM)
		for field in REQUIRED:
			with self.subTest(field=field):
				doc = self.completed()
				with set_user(self.technician):
					doc.set(field, None)
					doc.save()
					self.assertIn(f"{meta.get_field(field).label}: required.", doc.missing())

	def test_optional_answers_do_not(self):
		for field in OPTIONAL:
			with self.subTest(field=field):
				doc = self.completed()
				with set_user(self.technician):
					doc.set(field, None)
					doc.save()
					self.assertEqual(doc.missing(), [])


class TestEvidenceAndSecrets(BellaBotInstallationTestCase):
	def test_photos_and_trainees_are_required(self):
		meta = frappe.get_meta(FORM)
		for field in ("arrival_photos", "installation_photos", "trainees"):
			with self.subTest(field=field):
				doc = self.completed()
				with set_user(self.technician):
					doc.set(field, [])
					doc.save()
					self.assertEqual(doc.missing(), [f"{meta.get_field(field).label}: at least 1 needed."])

	def test_a_photo_must_be_a_private_file_of_this_form(self):
		public = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"{frappe.generate_hash(length=8)}.png",
				"is_private": 0,
				"content": frappe.generate_hash().encode(),
				"attached_to_doctype": FORM,
				"attached_to_name": self.name,
			}
		).insert(ignore_permissions=True)
		with set_user(self.technician), self.assertRaises(frappe.ValidationError):
			doc = self.doc()
			doc.append("arrival_photos", {"image": public.file_url})
			doc.save()

	def test_no_credentials_in_text(self):
		for field, text in (
			("setup_notes", "Wi-Fi password: Secret1"),
			("map_notes", "PIN = 4455"),
			("customer_remarks", "pairing code: AB12CD"),
		):
			with self.subTest(field=field), set_user(self.technician):
				doc = self.doc()
				doc.set(field, text)
				with self.assertRaisesRegex(frappe.ValidationError, "do not enter passwords"):
					doc.save()


class TestMachines(BellaBotInstallationTestCase):
	def test_the_form_comes_from_the_delivered_machine(self):
		doc = self.doc()
		self.assertEqual((doc.item_code, doc.serial_no), (self.robot, "JOB-BB-1"))
		self.assertEqual(doc.technician, self.technician)

	def test_a_machine_completes_only_once_its_checklist_is_submitted(self):
		with set_user(self.technician):
			job_api.device_action(self.job, self.row, "start")
			with self.assertRaisesRegex(frappe.ValidationError, "Submit the checklist"):
				job_api.device_action(self.job, self.row, "complete")
		self.submitted()
		with set_user(self.technician):
			self.assertEqual(job_api.device_action(self.job, self.row, "complete"), "Completed")

	def test_a_rental_machine_from_a_subscription_gets_the_same_form(self):
		frappe.get_doc(FORM, self.name).delete(ignore_permissions=True)
		fx.make_serial("JOB-BB-2", self.robot)
		subscription = fx.make_subscription(self.customer).name
		with set_user(self.supervisor):
			allocation_api.reserve("JOB-BB-2", "Subscription", subscription)
		job = make_job("Subscription", subscription, assigned_technician=self.technician).name
		with set_user(self.supervisor):
			job_api.job_action(job, "start")
		with set_user(self.technician):
			job_api.job_action(job, "arrive")
		doc = frappe.get_doc(FORM, self.start(job))
		self.assertEqual((doc.item_code, doc.serial_no), (self.robot, "JOB-BB-2"))


class TestOtherAnswers(BellaBotInstallationTestCase):
	def blank_group(self, section):
		doc = self.completed()
		with set_user(self.technician):
			for field in doc.ANY_OF[section]:
				doc.set(field, 0)
			doc.save()
		return doc

	def test_filling_other_answers_a_group_without_a_tick(self):
		for section, other in OTHER_ANSWERS.items():
			with self.subTest(section=section):
				doc = self.blank_group(section)
				with set_user(self.technician):
					doc.set(other, "Something else")
					doc.save()
				self.assertEqual(doc.missing(), [])

	def test_a_blank_other_does_not(self):
		meta = frappe.get_meta(FORM)
		for section, other in OTHER_ANSWERS.items():
			with self.subTest(section=section):
				doc = self.blank_group(section)
				with set_user(self.technician):
					doc.set(other, "   ")
					doc.save()
				self.assertEqual(doc.missing(), [f"{meta.get_field(section).label}: tick at least one."])

	def test_only_the_groups_with_other_in_the_source_have_it(self):
		self.assertEqual(self.doc().OTHER_ANSWERS, OTHER_ANSWERS)
		self.assertEqual(set(self.doc().ANY_OF) - set(OTHER_ANSWERS), {"modes_section"})

	def test_the_app_is_told_which_field_is_the_other_answer(self):
		fields = {f["fieldname"]: f for s in layout.sections(self.doc()) for f in s["fields"]}
		for other in OTHER_ANSWERS.values():
			with self.subTest(field=other):
				self.assertTrue(fields[other]["any_of_other"])
		self.assertNotIn("any_of_other", fields["step_delivery"])

	def test_each_other_box_sits_in_its_own_group(self):
		sections = {s["name"]: [f["fieldname"] for f in s["fields"]] for s in layout.sections(self.doc())}
		for section, other in OTHER_ANSWERS.items():
			with self.subTest(section=section):
				self.assertIn(other, sections[section])

	def test_other_deployment_type_needs_its_text(self):
		meta = frappe.get_meta(FORM)
		doc = self.completed()
		with set_user(self.technician):
			doc.deployment_type = "Other"
			doc.save()
			self.assertEqual(doc.missing(), [f"{meta.get_field('deployment_type_other').label}: required."])
			doc.deployment_type_other = "Temporary event"
			doc.save()
			self.assertEqual(doc.missing(), [])

	def test_no_credentials_in_an_other_answer(self):
		with (
			set_user(self.technician),
			self.assertRaisesRegex(frappe.ValidationError, "do not enter passwords"),
		):
			doc = self.doc()
			doc.advisories_other = "Wi-Fi password: Secret1"
			doc.save()

	def test_a_form_started_on_the_earlier_version_cannot_be_submitted(self):
		doc = self.completed()
		frappe.db.set_value(FORM, doc.name, "form_version", 1)
		with set_user(self.technician), self.assertRaisesRegex(frappe.ValidationError, "form version 1"):
			self.doc().submit()


class TestRequiredExplanations(BellaBotInstallationTestCase):
	def assert_needs(self, field, **answers):
		label = frappe.get_meta(FORM).get_field(field).label
		doc = self.completed()
		with set_user(self.technician):
			doc.update(answers)
			doc.save()
			self.assertIn(f"{label}: required.", doc.missing())
			with self.assertRaises(frappe.ValidationError):
				doc.submit()
			doc.reload()
			doc.set(field, "Explained")
			doc.save()
			self.assertEqual(doc.missing(), [])

	def test_a_failed_mode_test_needs_test_notes(self):
		for mode in MODE_TESTS:
			with self.subTest(mode=mode):
				self.assert_needs("test_notes", **{mode: "Fail", "test_notes": None})

	def test_not_tested_needs_no_notes(self):
		doc = self.completed()
		with set_user(self.technician):
			doc.delivery_status = "Not Tested"
			doc.save()
		self.assertEqual(doc.missing(), [])

	def test_moderate_or_severe_damage_needs_a_note(self):
		for damage in ("Moderate damage", "Severe damage"):
			with self.subTest(damage=damage):
				self.assert_needs("damage_note", visible_damage=damage, damage_note=None)

	def test_lighter_damage_needs_no_note(self):
		for damage in ("No damage", "Minor cosmetic damage"):
			with self.subTest(damage=damage):
				doc = self.completed()
				with set_user(self.technician):
					doc.visible_damage = damage
					doc.save()
				self.assertEqual(doc.missing(), [])

	def test_a_failed_safety_test_needs_details(self):
		self.assert_needs("safety_failure_details", safety_result="FAIL", safety_failure_details=None)

	def test_no_handover_needs_customer_remarks(self):
		self.assert_needs("customer_remarks", handover_confirmed="No", customer_remarks=None)

	def test_failed_mode_tests_and_damage_do_not_block_the_machine(self):
		self.act(self.technician, "start")
		self.submitted(
			delivery_status="Fail",
			test_notes="Tray sensor",
			visible_damage="Severe damage",
			damage_note="Dent",
		)
		self.assertEqual(self.status(), "In Progress")
		self.assertEqual(self.act(self.technician, "complete"), "Completed")


class BlockingAnswers:
	"""The same rules for each answer that blocks the machine; a subclass sets ANSWERS and TEXT."""

	ANSWERS: dict
	TEXT: str

	def submit_blocking(self):
		return self.submitted(**self.ANSWERS)

	def test_submitting_blocks_the_machine_with_the_explanation_as_reason(self):
		self.act(self.technician, "start")
		self.submit_blocking()
		self.assertEqual(self.status(), "Blocked")
		log = self.log()
		self.assertEqual(
			(log.action, log.from_status, log.to_status, log.user),
			("machine: block", "In Progress", "Blocked", self.technician),
		)
		self.assertIn(self.TEXT, log.reason)

	def test_a_machine_not_yet_started_is_blocked_too(self):
		self.submit_blocking()
		self.assertEqual(self.status(), "Blocked")

	def test_the_job_cannot_go_to_review(self):
		self.submit_blocking()
		with set_user(self.technician), self.assertRaisesRegex(frappe.ValidationError, "is blocked"):
			job_api.job_action(self.job, "submit")

	def test_the_technician_cannot_clear_it(self):
		self.submit_blocking()
		with self.assertRaises(frappe.PermissionError):
			self.act(self.technician, "unblock", "I fixed it")
		self.assertEqual(self.status(), "Blocked")

	def test_clearing_needs_a_reason_then_the_machine_can_complete(self):
		self.submit_blocking()
		for user in (self.supervisor, self.manager):
			with (
				self.subTest(user=user),
				self.assertRaisesRegex(frappe.ValidationError, "reason is required"),
			):
				self.act(user, "unblock")
		self.assertEqual(self.act(self.supervisor, "unblock", "Retested on site"), "In Progress")
		log = self.log()
		self.assertEqual(
			(log.action, log.user, log.reason), ("machine: unblock", self.supervisor, "Retested on site")
		)
		self.assertEqual(self.act(self.technician, "complete"), "Completed")

	def test_the_manager_can_clear_it_as_well(self):
		self.submit_blocking()
		self.assertEqual(self.act(self.manager, "unblock", "Accepted the risk"), "In Progress")

	def test_an_out_of_scope_supervisor_cannot_clear_it(self):
		self.submit_blocking()
		profile = frappe.get_doc("DeployOps Equipment Access Profile", {"user": self.supervisor})
		profile.categories = [c for c in profile.categories if c.category != self.robot_category()]
		profile.save(ignore_permissions=True)
		with self.assertRaises(frappe.PermissionError):
			self.act(self.supervisor, "unblock", "Not my equipment")
		self.assertEqual(self.status(), "Blocked")

	def test_the_answers_reach_both_reports(self):
		doc = self.submit_blocking()
		for audience in report.AUDIENCES:
			with self.subTest(audience=audience):
				self.assertIn(self.TEXT, report.render_html(self.doc(), audience))
		self.assertEqual(doc.docstatus, 1)

	def robot_category(self):
		return frappe.db.get_value("DeployOps Equipment Category Item", {"item_code": self.robot}, "parent")


class TestSafetyFail(BlockingAnswers, BellaBotInstallationTestCase):
	ANSWERS = {"safety_result": "FAIL", "safety_failure_details": "Emergency stop too slow"}  # noqa: RUF012
	TEXT = "Emergency stop too slow"


class TestHandoverNo(BlockingAnswers, BellaBotInstallationTestCase):
	ANSWERS = {"handover_confirmed": "No", "customer_remarks": "Manager absent, refused to accept"}  # noqa: RUF012
	TEXT = "Manager absent, refused to accept"


class TestOutcomes(BellaBotInstallationTestCase):
	def test_pass_and_yes_leave_the_machine_free(self):
		self.submitted()
		self.assertEqual(self.status(), "Pending")

	def test_both_failures_are_in_the_reason(self):
		self.submitted(
			safety_result="FAIL",
			safety_failure_details="No warning tone",
			handover_confirmed="No",
			customer_remarks="Wants it retested",
		)
		self.assertEqual(self.status(), "Blocked")
		self.assertIn("No warning tone", self.log().reason)
		self.assertIn("Wants it retested", self.log().reason)

	def test_a_replacement_form_blocks_a_completed_machine(self):
		self.act(self.technician, "start")
		self.submitted()
		self.act(self.technician, "complete")
		with set_user(self.manager):
			checklist_api.cancel_checklist(FORM, self.name, "Survey repeated")
		doc = frappe.get_doc(FORM, self.start(self.job))
		with set_user(self.technician):
			doc = self.complete(doc)
			doc.update({"safety_result": "FAIL", "safety_failure_details": "Found on recheck"})
			doc.save()
			doc.submit()
		self.assertEqual(self.status(), "Blocked")
		self.assertEqual((self.log().from_status, self.log().to_status), ("Completed", "Blocked"))

	def test_cancelling_a_failed_form_leaves_the_machine_blocked(self):
		self.submitted(safety_result="FAIL", safety_failure_details="Bumper")
		with set_user(self.manager):
			checklist_api.cancel_checklist(FORM, self.name, "Survey repeated")
		self.assertEqual(self.status(), "Blocked")

	def test_a_manual_block_on_a_draft_clears_without_a_reason(self):
		self.act(self.technician, "block", "Stairs on the route")
		self.assertEqual(self.act(self.supervisor, "unblock"), "In Progress")


class TestReviewFixes(BellaBotInstallationTestCase):
	def test_a_new_failure_on_an_already_blocked_machine_is_logged(self):
		self.act(self.technician, "block", "Stairs on the route")
		self.submitted(safety_result="FAIL", safety_failure_details="Bumper loose")
		self.assertEqual(self.status(), "Blocked")
		log = self.log()
		self.assertEqual(
			(log.action, log.from_status, log.to_status), ("machine: block", "Blocked", "Blocked")
		)
		self.assertIn("Bumper loose", log.reason)

	def test_clearing_still_needs_a_reason_once_the_form_was_cancelled(self):
		self.submitted(safety_result="FAIL", safety_failure_details="Bumper")
		with set_user(self.manager):
			checklist_api.cancel_checklist(FORM, self.name, "Survey repeated")
		with self.assertRaisesRegex(frappe.ValidationError, "reason is required"):
			self.act(self.supervisor, "unblock")
		self.assertEqual(self.act(self.supervisor, "unblock", "Retested"), "In Progress")

	def test_clearing_still_needs_a_reason_after_a_passing_replacement(self):
		self.submitted(safety_result="FAIL", safety_failure_details="Bumper")
		with set_user(self.manager):
			checklist_api.cancel_checklist(FORM, self.name, "Survey repeated")
		doc = frappe.get_doc(FORM, self.start(self.job))
		with set_user(self.technician):
			self.complete(doc).save()
			doc.submit()
		self.assertEqual(self.status(), "Blocked")
		with self.assertRaisesRegex(frappe.ValidationError, "reason is required"):
			self.act(self.supervisor, "unblock")

	def test_the_flag_resets_once_cleared(self):
		self.submitted(safety_result="FAIL", safety_failure_details="Bumper")
		self.act(self.supervisor, "unblock", "Retested")
		self.act(self.technician, "block", "Stairs on the route")
		self.assertEqual(self.act(self.supervisor, "unblock"), "In Progress")

	def test_nobody_can_set_or_clear_the_flag_by_editing_the_job(self):
		self.submitted(safety_result="FAIL", safety_failure_details="Bumper")
		with set_user(self.supervisor), self.assertRaisesRegex(frappe.ValidationError, "job workflow"):
			job = frappe.get_doc(JOB, self.job)
			job.devices[0].blocked_by_checklist = 0
			job.save()

	def test_a_completed_machine_without_a_submitted_form_cannot_go_to_review(self):
		self.act(self.technician, "start")
		self.submitted()
		self.act(self.technician, "complete")
		with set_user(self.manager):
			checklist_api.cancel_checklist(FORM, self.name, "Survey repeated")
		with set_user(self.technician), self.assertRaisesRegex(frappe.ValidationError, "not submitted"):
			job_api.job_action(self.job, "submit")
		self.start(self.job)
		with set_user(self.technician), self.assertRaisesRegex(frappe.ValidationError, "not submitted"):
			job_api.job_action(self.job, "submit")

	def test_a_manager_discards_an_outdated_draft_and_a_new_form_starts(self):
		frappe.db.set_value(FORM, self.name, "form_version", 1)
		with set_user(self.technician), self.assertRaises(frappe.PermissionError):
			checklist_api.cancel_checklist(FORM, self.name, "Old form")
		with set_user(self.manager):
			checklist_api.cancel_checklist(FORM, self.name, "Old form version")
		self.assertFalse(frappe.db.exists(FORM, self.name))
		log = self.log()
		self.assertEqual(log.action, "checklist: draft discarded")
		self.assertIn("Old form version", log.reason)
		new = self.start(self.job)
		self.assertEqual(self.doc_named(new).form_version, self.doc_named(new).FORM_VERSION)

	def test_a_current_draft_cannot_be_discarded(self):
		with set_user(self.manager), self.assertRaisesRegex(frappe.ValidationError, "outdated draft"):
			checklist_api.cancel_checklist(FORM, self.name, "Changed my mind")
		self.assertTrue(frappe.db.exists(FORM, self.name))

	def test_the_app_is_told_which_answers_require_a_field(self):
		fields = {f["fieldname"]: f for s in layout.sections(self.doc()) for f in s["fields"]}
		self.assertEqual(
			fields["safety_failure_details"]["required_when"], [{"field": "safety_result", "value": "FAIL"}]
		)
		self.assertEqual(len(fields["test_notes"]["required_when"]), 4)
		self.assertFalse(fields["safety_failure_details"]["reqd"])

	def doc_named(self, name):
		return frappe.get_doc(FORM, name)


class TestDocuments(BellaBotInstallationTestCase):
	def test_every_source_document_ships_with_the_app_in_a_real_section(self):
		root = Path(frappe.get_app_path("deployops", "reference_files"))
		sections = {df.fieldname for df in frappe.get_meta(FORM).fields if df.fieldtype == "Section Break"}
		self.assertEqual(
			{filename for filename, _title, _section in install.BELLABOT_INSTALLATION_REFERENCES},
			{
				"bellabot-deployment-manual.pdf",
				"bellabot-operation-guide.pdf",
				"bellabot-maintenance-and-care.png",
			},
		)
		for filename, _title, section in install.BELLABOT_INSTALLATION_REFERENCES:
			with self.subTest(file=filename):
				self.assertTrue((root / filename).is_file())
				self.assertIn(section, sections)

	def test_a_new_install_lists_them_as_private_files(self):
		settings = frappe.get_single("DeployOps Reference Files")
		settings.set("references", [])
		settings.seeded_references = None
		settings.save(ignore_permissions=True)
		install.sync_reference_files()
		rows = [
			row
			for row in frappe.get_single("DeployOps Reference Files").references
			if row.checklist == install.BELLABOT_INSTALLATION
		]
		self.assertEqual(
			[(row.title, row.section) for row in rows],
			[(title, section) for _file, title, section in install.BELLABOT_INSTALLATION_REFERENCES],
		)
		for row in rows:
			with self.subTest(title=row.title):
				self.assertTrue(frappe.db.get_value("File", {"file_url": row.file}, "is_private"))


class TestReport(BellaBotInstallationTestCase):
	def test_both_reports_show_the_answers_and_other_text(self):
		self.submitted(safety_other="Ramp check", map_name="Ground floor")
		self.assertIn(FORM, report.REPORTABLE)
		for audience in report.AUDIENCES:
			with self.subTest(audience=audience):
				html = report.render_html(self.doc(), audience)
				self.assertIn("Ramp check", html)
				self.assertIn("Ground floor", html)

	def test_the_customer_copy_leaves_out_the_audit_trail(self):
		doc = self.submitted()
		self.assertIn(self.job, report.render_html(self.doc(), "internal"))
		self.assertNotIn(self.job, report.render_html(self.doc(), "customer"))
		self.assertEqual(doc.docstatus, 1)

	def test_desk_print_formats_render_the_same_report(self):
		self.submitted()
		for print_format, kind in (
			("BellaBot Installation Report", "Internal report"),
			("BellaBot Installation Report (Customer)", "Customer copy"),
		):
			with self.subTest(print_format=print_format):
				self.assertIn(kind, frappe.get_print(FORM, self.name, print_format, doc=self.doc()))

	def test_a_draft_has_no_report(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Only a submitted checklist"):
			report.render_html(self.doc())


class TestTwoMachines(ChecklistTestCase):
	def test_each_delivered_machine_has_its_own_form_and_outcome(self):
		fx.make_serial("JOB-BB-2", self.robot)
		bundle = fx.make_bundle(self.robot, ["JOB-BB-1", "JOB-BB-2"])
		note = fx.make_delivery_note(
			self.customer, [{"item_code": self.robot, "serial_and_batch_bundle": bundle}]
		)
		job = make_job("Delivery Note", note.name, assigned_technician=self.technician).name
		with set_user(self.supervisor):
			job_api.job_action(job, "start")
		with set_user(self.technician):
			job_api.job_action(job, "arrive")
			first, second = frappe.get_doc(JOB, job).devices
			names = [checklist_api.start_checklist(job, row.name)["name"] for row in (first, second)]
			doc = self.complete(frappe.get_doc(FORM, names[0]))
			doc.save()
			doc.submit()
			job_api.device_action(job, first.name, "start")
			self.assertEqual(job_api.device_action(job, first.name, "complete"), "Completed")
			blocked = self.complete(frappe.get_doc(FORM, names[1]))
			blocked.update({"safety_result": "FAIL", "safety_failure_details": "Bumper"})
			blocked.save()
			blocked.submit()
			with self.assertRaisesRegex(frappe.ValidationError, "is blocked"):
				job_api.job_action(job, "submit")
			self.assertEqual(
				[
					frappe.db.get_value("DeployOps Job Device", r.name, "device_status")
					for r in (first, second)
				],
				["Completed", "Blocked"],
			)
		self.assertEqual(
			[frappe.db.get_value(FORM, name, ["serial_no", "docstatus"]) for name in names],
			[("JOB-BB-1", 1), ("JOB-BB-2", 1)],
		)


class TestSubmittedRecord(BellaBotInstallationTestCase):
	def test_submit_locks_the_form_with_signers_and_snapshot(self):
		self.submitted()
		doc = self.doc()
		self.assertEqual(doc.docstatus, 1)
		record = {row.signature_field: row for row in doc.signatures}
		self.assertEqual(record["customer_signature"].signer_name, doc.customer_signatory)
		self.assertEqual(record["technician_signature"].signer_name, get_fullname(self.technician))
		snapshot = frappe.parse_json(doc.submission_snapshot)
		self.assertEqual(snapshot["form_version"], doc.FORM_VERSION)
		self.assertEqual(snapshot["values"]["map_name"], doc.map_name)
		with set_user(self.technician), self.assertRaises(frappe.ValidationError):
			doc.map_name = "changed after submit"
			doc.save()

	def test_the_customer_signature_needs_its_signer(self):
		doc = self.completed()
		with set_user(self.technician):
			doc.customer_signatory = None
			doc.save()
			self.assertIn("Customer signature: the signer's name is required.", doc.missing())

	def test_only_people_on_the_job_can_read_the_form(self):
		other = "_bellabot-tech@deployops.test"
		if not frappe.db.exists("User", other):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": other,
					"first_name": "Other",
					"send_welcome_email": 0,
					"roles": [{"role": "DeployOps Technician"}],
				}
			).insert(ignore_permissions=True)
		for user, allowed in (
			(self.technician, True),
			(self.supervisor, True),
			(self.manager, True),
			(other, False),
			("Guest", False),
		):
			with self.subTest(user=user):
				self.assertEqual(bool(frappe.has_permission(FORM, "read", self.name, user=user)), allowed)
