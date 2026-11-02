"""BellaBot on-site installation checklist (#25): tests of the form as it stands.

Source: https://form.jotform.com/262743396548066, read from the published form on 2026-11-02.
"""

import frappe
from frappe.tests.classes.context_managers import set_user
from frappe.utils import get_fullname

from deployops.api import checklists as checklist_api
from deployops.api import jobs as job_api
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

	def submitted(self):
		doc = self.completed()
		with set_user(self.technician):
			doc.submit()
		return doc


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

	def test_a_failed_safety_test_does_not_block_by_itself(self):
		"""Only a final_decision field drives the machine; other answers are an open product decision."""
		doc = self.completed()
		with set_user(self.technician):
			doc.safety_result = "FAIL"
			doc.save()
			doc.submit()
		self.assertEqual(frappe.db.get_value("DeployOps Job Device", self.row, "device_status"), "Pending")


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
			job_api.device_action(job, second.name, "block", "Stairs on the route")
			with self.assertRaisesRegex(frappe.ValidationError, "is blocked"):
				job_api.job_action(job, "submit")
		self.assertEqual(
			[frappe.db.get_value(FORM, name, ["serial_no", "docstatus"]) for name in names],
			[("JOB-BB-1", 1), ("JOB-BB-2", 0)],
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
