"""Cashmatic pre-installation checklist (#22): acceptance tests, one per requirement of the feature.

Field-by-field mapping against the original Jotform: docs/CASHMATIC_PREINSTALLATION_MAPPING.md.
UAT scenarios that walk the same requirements by hand: docs/CASHMATIC_PREINSTALLATION_UAT.md.
"""

import frappe
from frappe.tests.classes.context_managers import set_user
from frappe.utils import get_fullname

from deployops.api import checklists as checklist_api
from deployops.api import jobs as job_api
from deployops.api import technician as technician_api
from deployops.install import BUNDLED_REFERENCES
from deployops.tests import erpnext_fixtures as fx
from deployops.tests.test_checklists import ChecklistTestCase
from deployops.tests.test_job import JOB, make_job

FORM = "DeployOps Cashmatic Pre-installation"
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
# Ticked steps per section, as in the source: every option of each Jotform checkbox group is required.
SOURCE_STEPS = {
	"Shared documents prior to the visit": 4,
	"Employee checklist": 12,
	"Machine configuration steps": 7,
	"Machine activation steps": 9,
}


def steps_by_section() -> dict[str, list]:
	sections, current = {}, None
	for df in frappe.get_meta(FORM).fields:
		if df.fieldtype == "Section Break":
			current = df.label
		elif df.fieldtype == "Check":
			sections.setdefault(current, []).append(df)
	return sections


class PreinstallationTestCase(ChecklistTestCase):
	def setUp(self):
		super().setUp()
		self.job = self.working_job("Pre-installation")
		self.set_serial(self.job, 0, "JOB-CR-1")
		self.name = self.start(self.job)

	def set_serial(self, job, index, serial):
		with set_user(self.technician):
			doc = frappe.get_doc(JOB, job)
			doc.devices[index].serial_no = serial
			doc.save()

	def doc(self):
		return frappe.get_doc(FORM, self.name)

	def completed(self):
		with set_user(self.technician):
			doc = self.complete(self.doc())
			doc.save()
		return doc


class TestSourceContent(PreinstallationTestCase):
	def test_every_source_step_is_a_required_tick_in_its_section(self):
		"""Documents, readiness, labeling/accessories, CDIG/F1/F2 configuration, activation."""
		sections = steps_by_section()
		self.assertEqual({label: len(steps) for label, steps in sections.items()}, SOURCE_STEPS)
		self.assertTrue(all(df.reqd for steps in sections.values() for df in steps))
		labels = " ".join(df.label for steps in sections.values() for df in steps)
		for phrase in (
			"MAXIMUM LEVEL",
			"FLOAT LEVEL",
			"ACCEPTED DENOMINATIONS",
			"email notifications",
			"PRINTED NOTIFICATIONS",
			"(F1)",
			"(F2)",
			"PAIR DEVICE",
			"Logo and QR code",
			"cashbox keys",
		):
			self.assertIn(phrase, labels)

	def test_each_unticked_step_stops_the_submit(self):
		for label, steps in steps_by_section().items():
			with self.subTest(section=label):
				doc = self.completed()
				with set_user(self.technician):
					doc.set(steps[-1].fieldname, 0)
					doc.save()
					self.assertEqual(doc.missing(), [f"{steps[-1].label}: not ticked."])
					with self.assertRaises(frappe.ValidationError):
						doc.submit()

	def test_machine_details_evidence_hours_remarks_and_signature_are_required(self):
		required = {
			"software_version": "Software version",
			"firmware_version": "Firmware version",
			"activation_date": "Activation date",
			"preparation_photos": "Photos (after setup, ready for delivery)",
			"special_installation_request": "Special installation request",
			"additional_remarks": "Additional remarks",
			"employee_signature": "Employee signature",
		}
		for field, label in required.items():
			with self.subTest(field=field):
				doc = self.completed()
				with set_user(self.technician):
					doc.set(field, [] if field == "preparation_photos" else None)
					doc.save()
					self.assertEqual(len(doc.missing()), 1)
					self.assertTrue(doc.missing()[0].startswith(label))

	def test_reference_manuals_are_bundled_for_real_sections_of_the_form(self):
		sections = {df.fieldname for df in frappe.get_meta(FORM).fields if df.fieldtype == "Section Break"}
		for filename, _title, section in BUNDLED_REFERENCES:
			with self.subTest(file=filename):
				self.assertIn(section, sections)
		bundled = {filename for filename, _title, _section in BUNDLED_REFERENCES}
		for source_pdf in (  # one per PDF embedded in the Jotform
			"user-manual.pdf",
			"web-interface.pdf",
			"my-cashmatic-app.pdf",
			"device-installation-guide.pdf",
			"parts-manual.pdf",
			"device-configuration.pdf",
			"user-setup.pdf",
		):
			self.assertIn(source_pdf, bundled)


class TestMachineAndSerial(PreinstallationTestCase):
	def test_device_comes_from_the_item_on_the_job(self):
		self.assertEqual(self.doc().device_model, frappe.db.get_value("Item", self.cash, "item_name"))
		self.assertTrue(frappe.get_meta(FORM).get_field("device_model").read_only)

	def test_serial_is_assigned_before_preparation_completes(self):
		job = self.working_job("Pre-installation")  # an undelivered order: no serial yet
		name = self.start(job)
		row = frappe.get_doc(JOB, job).devices[0].name
		with set_user(self.technician):
			doc = self.complete(frappe.get_doc(FORM, name))
			doc.save()
			with self.assertRaises(frappe.ValidationError):  # the checklist can't be submitted
				doc.submit()
			job_api.device_action(job, row, "start")
			with self.assertRaisesRegex(frappe.ValidationError, "needs a Serial No"):
				job_api.device_action(job, row, "complete")  # nor the machine completed

		self.set_serial(job, 0, "JOB-CR-2")
		with set_user(self.technician):  # straight to Submit, no edit in between
			self.assertEqual(technician_api.submit_form(FORM, name), {"docstatus": 1})
			self.assertEqual(job_api.device_action(job, row, "complete"), "Completed")
		self.assertEqual(frappe.db.get_value(FORM, name, "serial_no"), "JOB-CR-2")

	def test_two_machines_on_one_order_get_their_own_checklists(self):
		order = fx.make_sales_order(self.customer, [self.cash, self.cash]).name
		job = make_job(
			"Sales Order", order, job_type="Pre-installation", assigned_technician=self.technician
		).name
		with set_user(self.supervisor):
			job_api.job_action(job, "start")
		self.set_serial(job, 0, "JOB-CR-2")
		self.set_serial(job, 1, "JOB-CR-3")
		rows = [row.name for row in frappe.get_doc(JOB, job).devices]
		with set_user(self.technician):
			first, second = (checklist_api.start_checklist(job, row)["name"] for row in rows)
			doc = self.complete(frappe.get_doc(FORM, first))
			doc.save()
			doc.submit()
		self.assertEqual(
			[frappe.db.get_value(FORM, name, ["serial_no", "docstatus"]) for name in (first, second)],
			[("JOB-CR-2", 1), ("JOB-CR-3", 0)],  # one prepared, the other still open
		)


class TestWorkingHours(PreinstallationTestCase):
	def test_seven_fixed_days_each_open_and_close_or_closed(self):
		doc = self.completed()
		self.assertEqual([row.day for row in doc.working_hours], DAYS)
		with set_user(self.technician):
			doc.working_hours[6].update({"open_time": None, "close_time": None, "closed": 1})
			doc.working_hours[0].close_time = None
			doc.save()
			self.assertEqual(doc.missing(), ["Working hours, Monday: opening and closing time, or Closed."])

			doc.working_hours[0].day = "Holiday"
			with self.assertRaises(frappe.ValidationError):
				doc.save()


class TestEvidenceAndSecrets(PreinstallationTestCase):
	def test_preparation_photos_must_be_private_files_of_this_form(self):
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
		other_form = self.start(self.working_job("Pre-installation", serial="JOB-CR-2"))
		foreign = self.attach(FORM, other_form)[0]
		for case, url in (("public", public.file_url), ("another form's", foreign)):
			with (
				self.subTest(case=case),
				set_user(self.technician),
				self.assertRaises(frappe.ValidationError),
			):
				doc = self.doc()
				doc.append("preparation_photos", {"image": url})
				doc.save()

	def test_no_credentials_or_activation_codes_in_text(self):
		for field, text in (
			("additional_remarks", "Admin user created, password: Secret1"),
			("special_installation_request", "Wall mounted. OTP = 123456"),
			("additional_remarks", "pairing code: AB12CD"),
			("software_version", "PIN: 4455"),
		):
			with self.subTest(field=field, text=text), set_user(self.technician):
				doc = self.doc()
				doc.set(field, text)
				with self.assertRaisesRegex(frappe.ValidationError, "do not enter passwords"):
					doc.save()


class TestSubmittedRecord(PreinstallationTestCase):
	def test_submit_locks_the_form_with_signer_and_snapshot(self):
		doc = self.completed()
		with set_user(self.technician):
			doc.submit()
		doc = self.doc()
		self.assertEqual(doc.docstatus, 1)
		record = {row.signature_field: row for row in doc.signatures}["employee_signature"]
		name = get_fullname(self.technician)
		self.assertEqual((record.signer_name, record.captured_by), (name, self.technician))
		snapshot = frappe.parse_json(doc.submission_snapshot)
		self.assertEqual(snapshot["form_version"], doc.FORM_VERSION)
		self.assertEqual(snapshot["values"]["software_version"], doc.software_version)
		self.assertEqual(snapshot["signatures"]["employee_signature"]["signer_name"], name)
		with set_user(self.technician), self.assertRaises(frappe.ValidationError):
			doc.additional_remarks = "changed after submit"
			doc.save()

	def test_only_people_on_the_job_can_read_the_form(self):
		other = "_preinstall-tech@deployops.test"
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
		with set_user(other), self.assertRaises(frappe.PermissionError):
			checklist_api.start_checklist(self.job, frappe.get_doc(JOB, self.job).devices[0].name)
