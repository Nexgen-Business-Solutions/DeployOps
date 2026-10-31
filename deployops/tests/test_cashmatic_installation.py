"""Cashmatic on-site installation checklist (#23): acceptance tests, one per requirement of the feature.

Field-by-field mapping against the original Jotform: docs/CASHMATIC_INSTALLATION_MAPPING.md.
UAT scenarios that walk the same requirements by hand: docs/CASHMATIC_INSTALLATION_UAT.md.
"""

import io

import frappe
from frappe.tests.classes.context_managers import set_user
from frappe.utils import get_fullname

from deployops.api import checklists as checklist_api
from deployops.api import jobs as job_api
from deployops.api import reports as reports_api
from deployops.api import technician as technician_api
from deployops.checklists import report
from deployops.install import INSTALLATION_REFERENCES
from deployops.tests import erpnext_fixtures as fx
from deployops.tests.test_checklists import VALID_SIGNATURE, ChecklistTestCase
from deployops.tests.test_job import JOB, make_job

FORM = "DeployOps Cashmatic Installation"
# Sections whose every step is a required tick (the on-site Jotform's checkbox groups).
REQUIRED_STEPS = {
	"Machine positioning evaluation": 8,
	"Power and network": 5,
	"Verifications": 2,
	"Preparing the machine": 4,
	"Customer training": 9,
}
# Sections where at least one step must be ticked (the Jotform's "Checkbox in Dropdown" widgets).
AT_LEAST_ONE_STEPS = {
	"Web panel explanation": 12,
	"Firsthand training": 13,
	"Problem solving": 3,
	"Warnings and precautions": 4,
}


def steps_by_section() -> dict[str, list]:
	sections, current = {}, None
	for df in frappe.get_meta(FORM).fields:
		if df.fieldtype == "Section Break":
			current = df.label
		elif df.fieldtype == "Check":
			sections.setdefault(current, []).append(df)
	return sections


def real_photo(name: str, shade: int) -> str:
	"""A real image, different each time: the report decodes it and Frappe de-duplicates equal files."""
	from PIL import Image

	buffer = io.BytesIO()
	Image.new("RGB", (64, 64), (shade, 120, 200)).save(buffer, "PNG")
	return (
		frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"{frappe.generate_hash(length=8)}.png",
				"is_private": 1,
				"content": buffer.getvalue(),
				"attached_to_doctype": FORM,
				"attached_to_name": name,
			}
		)
		.insert(ignore_permissions=True)
		.file_url
	)


class InstallationTestCase(ChecklistTestCase):
	def setUp(self):
		super().setUp()
		self.job = self.working_job()
		self.name = self.start(self.job)

	def doc(self):
		return frappe.get_doc(FORM, self.name)

	def completed(self):
		with set_user(self.technician):
			doc = self.complete(self.doc())
			doc.save()
		return doc


class TestSourceContent(InstallationTestCase):
	def test_every_source_step_is_in_its_section_with_the_right_rule(self):
		sections = steps_by_section()
		self.assertEqual(
			{label: len(steps) for label, steps in sections.items()}, REQUIRED_STEPS | AT_LEAST_ONE_STEPS
		)
		for label in REQUIRED_STEPS:
			self.assertTrue(all(df.reqd for df in sections[label]), label)
		for label in AT_LEAST_ONE_STEPS:
			self.assertFalse(any(df.reqd for df in sections[label]), label)

	def test_each_unticked_required_step_stops_the_submit(self):
		sections = steps_by_section()
		for label in REQUIRED_STEPS:
			step = sections[label][-1]
			with self.subTest(section=label):
				doc = self.completed()
				with set_user(self.technician):
					doc.set(step.fieldname, 0)
					doc.save()
					self.assertEqual(doc.missing(), [f"{step.label}: not ticked."])
					with self.assertRaises(frappe.ValidationError):
						doc.submit()

	def test_each_group_needs_at_least_one_tick(self):
		sections = steps_by_section()
		for label in AT_LEAST_ONE_STEPS:
			with self.subTest(section=label):
				doc = self.completed()
				with set_user(self.technician):
					for step in sections[label]:
						doc.set(step.fieldname, 0)
					doc.save()
					self.assertEqual(doc.missing(), [f"{label}: tick at least one."])

	def test_details_keys_and_sign_off_are_required(self):
		for field in (
			"network_type",
			"ip_address",
			"software_version",
			"firmware_version",
			"pos_integration",
			"installed_on",
			"condition_at_delivery",
			"keys_receiver_name",
			"keys_receiver_signature",
			"keys_handover_date",
			"client_representative",
			"client_title",
			"client_department",
			"client_signature",
		):
			with self.subTest(field=field):
				doc = self.completed()
				self.assertEqual(doc.missing(), [])
				with set_user(self.technician):
					doc.set(field, None)
					doc.flags.ignore_mandatory = True
					doc.save()
					self.assertTrue(
						any(frappe.get_meta(FORM).get_field(field).label in p for p in doc.missing()),
						doc.missing(),
					)

	def test_cashbox_and_remarks_are_optional_as_in_the_source(self):
		doc = self.completed()
		self.assertFalse(doc.cashbox or doc.remarks)
		self.assertEqual(doc.missing(), [])

	def test_pos_details_are_required_only_with_pos_integration(self):
		doc = self.completed()
		with set_user(self.technician):
			doc.pos_integration = "Yes"
			doc.pos_brand = None
			doc.save()
			self.assertEqual(doc.missing(), ["POS brand / version: required."])
			doc.pos_integration = "No"
			doc.pos_connector = None
			doc.save()
			self.assertEqual(doc.missing(), [])

	def test_at_least_three_installation_photos(self):
		doc = self.completed()
		with set_user(self.technician):
			doc.set("installation_photos", doc.installation_photos[:2])
			doc.save()
			self.assertEqual(doc.missing(), ["Photos of installation: at least 3 needed."])

	def test_every_embedded_document_is_listed_in_a_real_section(self):
		sections = {df.fieldname for df in frappe.get_meta(FORM).fields if df.fieldtype == "Section Break"}
		for filename, _title, section in INSTALLATION_REFERENCES:
			with self.subTest(file=filename, section=section):
				self.assertIn(section, sections)
		self.assertEqual(
			{filename for filename, _title, _section in INSTALLATION_REFERENCES},
			{
				"device-installation-guide.pdf",
				"web-interface.pdf",
				"my-cashmatic-app.pdf",
				"warnings-precautions.pdf",
			},
		)


class TestMachineLevelAcceptance(InstallationTestCase):
	def test_machine_data_comes_from_the_delivery_on_the_job(self):
		doc = self.doc()
		self.assertEqual((doc.item_code, doc.serial_no), (self.cash, "JOB-CR-1"))
		with set_user(self.technician), self.assertRaises(frappe.ValidationError):
			doc.serial_no = "JOB-CR-2"
			doc.save()

	def test_two_machines_on_one_delivery_have_separate_outcomes(self):
		bundle = fx.make_bundle(self.cash, ["JOB-CR-2", "JOB-CR-3"])
		note = fx.make_delivery_note(
			self.customer, [{"item_code": self.cash, "serial_and_batch_bundle": bundle}]
		)
		job = make_job("Delivery Note", note.name, assigned_technician=self.technician).name
		with set_user(self.supervisor):
			job_api.job_action(job, "start")
		rows = [row.name for row in frappe.get_doc(JOB, job).devices]
		with set_user(self.technician):
			job_api.job_action(job, "arrive")
			first, second = (checklist_api.start_checklist(job, row)["name"] for row in rows)
			doc = self.complete(frappe.get_doc(FORM, first))
			doc.save()
			doc.submit()
			job_api.device_action(job, rows[0], "start")
			self.assertEqual(job_api.device_action(job, rows[0], "complete"), "Completed")
			job_api.device_action(job, rows[1], "block", "Power socket missing")
			with self.assertRaisesRegex(frappe.ValidationError, "is blocked"):
				job_api.job_action(job, "submit")
		self.assertEqual(
			[frappe.db.get_value(FORM, name, ["serial_no", "docstatus"]) for name in (first, second)],
			[("JOB-CR-2", 1), ("JOB-CR-3", 0)],
		)
		self.assertEqual(
			[row.device_status for row in frappe.get_doc(JOB, job).devices], ["Completed", "Blocked"]
		)

	def test_each_machine_needs_its_own_customer_signature(self):
		bundle = fx.make_bundle(self.cash, ["JOB-CR-2", "JOB-CR-3"])
		note = fx.make_delivery_note(
			self.customer, [{"item_code": self.cash, "serial_and_batch_bundle": bundle}]
		)
		job = make_job("Delivery Note", note.name, assigned_technician=self.technician).name
		with set_user(self.supervisor):
			job_api.job_action(job, "start")
		rows = [row.name for row in frappe.get_doc(JOB, job).devices]
		with set_user(self.technician):
			job_api.job_action(job, "arrive")
			first, second = (
				frappe.get_doc(FORM, checklist_api.start_checklist(job, row)["name"]) for row in rows
			)
			self.complete(first).save()
			first.submit()
			self.complete(second)
			second.client_signature = None
			second.save()
			self.assertEqual(second.missing(), ["Client representative signature: required."])
			with self.assertRaises(frappe.ValidationError):
				second.submit()
		self.assertIn("client_signature", [row.signature_field for row in first.signatures])

	def started_job(self, serials):
		bundle = fx.make_bundle(self.cash, serials)
		note = fx.make_delivery_note(
			self.customer, [{"item_code": self.cash, "serial_and_batch_bundle": bundle}]
		)
		job = make_job("Delivery Note", note.name, assigned_technician=self.technician).name
		with set_user(self.supervisor):
			job_api.job_action(job, "start")
		return job

	def test_starting_the_job_creates_each_machines_checklist(self):
		job = self.started_job(["JOB-CR-2", "JOB-CR-3"])
		self.assertEqual(frappe.db.get_value(JOB, job, "status"), "Ready for Deployment")
		forms = frappe.get_all(FORM, filters={"job": job}, pluck="serial_no", order_by="serial_no")
		self.assertEqual(forms, ["JOB-CR-2", "JOB-CR-3"])
		with set_user(self.technician):
			machines = technician_api.job_view(job)["machines"]
			self.assertEqual([m["checklist"]["doctype"] for m in machines], [FORM, FORM])
			doc = frappe.get_doc(FORM, machines[0]["checklist"]["name"])
			doc.remarks = "Filled in before arriving"
			doc.save()  # the assigned technician can work on it straight away

	def test_a_machine_without_a_form_can_start_one_before_arriving(self):
		"""A job started before this rule, or a machine added later: Start checklist still works."""
		job = self.started_job(["JOB-CR-2"])
		row = frappe.get_doc(JOB, job).devices[0].name
		frappe.delete_doc(FORM, frappe.db.get_value(FORM, {"job": job}), force=True, ignore_permissions=True)
		with set_user(self.technician):
			self.assertTrue(technician_api.job_view(job)["machines"][0]["can_start_checklist"])
			created = checklist_api.start_checklist(job, row)
		self.assertEqual(frappe.db.get_value(FORM, created["name"], "job_device"), row)

	def test_a_draft_job_has_no_checklist_yet(self):
		bundle = fx.make_bundle(self.cash, ["JOB-CR-2"])
		note = fx.make_delivery_note(
			self.customer, [{"item_code": self.cash, "serial_and_batch_bundle": bundle}]
		)
		job = make_job("Delivery Note", note.name, assigned_technician=self.technician).name
		self.assertFalse(frappe.db.exists(FORM, {"job": job}))

	def test_starting_a_pre_installation_job_creates_nothing(self):
		job = self.working_job("Pre-installation")
		self.assertFalse(frappe.db.exists("DeployOps Cashmatic Pre-installation", {"job": job}))

	def test_the_desk_job_page_has_no_checklist_connections(self):
		self.assertEqual(list(frappe.get_meta(JOB).links), [])

	def test_a_machine_completes_only_once_its_checklist_is_submitted(self):
		row = frappe.get_doc(JOB, self.job).devices[0].name
		doc = self.completed()
		with set_user(self.technician):
			job_api.device_action(self.job, row, "start")
			with self.assertRaisesRegex(frappe.ValidationError, "Submit the checklist"):
				job_api.device_action(self.job, row, "complete")
			doc.submit()
			self.assertEqual(job_api.device_action(self.job, row, "complete"), "Completed")


class TestEvidenceAndSecrets(InstallationTestCase):
	def test_installation_photos_must_be_private_files_of_this_form(self):
		other_form = self.start(self.working_job(serial="JOB-CR-2"))
		foreign = self.attach(FORM, other_form)[0]
		with set_user(self.technician), self.assertRaises(frappe.ValidationError):
			doc = self.doc()
			doc.append("installation_photos", {"image": foreign})
			doc.save()

	def test_no_credentials_in_text(self):
		for field, text in (
			("remarks", "Admin user created, password: Secret1"),
			("condition_at_delivery", "Good. PIN = 4455"),
			("pos_connector", "pairing code: AB12CD"),
			("ip_address", "OTP: 123456"),
		):
			with self.subTest(field=field, text=text), set_user(self.technician):
				doc = self.doc()
				doc.set(field, text)
				with self.assertRaisesRegex(frappe.ValidationError, "do not enter passwords"):
					doc.save()

	def test_each_signature_needs_its_signer_name(self):
		for signature, name_field, label in (
			("keys_receiver_signature", "keys_receiver_name", "Keys receiver name"),
			("client_signature", "client_representative", "Client representative"),
		):
			with self.subTest(signature=signature):
				doc = self.completed()
				with set_user(self.technician):
					doc.set(signature, VALID_SIGNATURE)
					doc.set(name_field, None)
					doc.save()
					self.assertIn(f"{label}: required.", doc.missing())
					self.assertTrue(any("signer's name" in problem for problem in doc.missing()))


class TestSubmittedRecord(InstallationTestCase):
	def test_submit_locks_the_form_with_signers_and_snapshot(self):
		doc = self.completed()
		with set_user(self.technician):
			doc.client_representative = "Ada Client"
			doc.client_signature = VALID_SIGNATURE
			doc.technician_signature = VALID_SIGNATURE
			doc.save()
			doc.submit()
		doc = self.doc()
		signers = {row.signature_field: row.signer_name for row in doc.signatures}
		self.assertEqual(
			signers,
			{
				"keys_receiver_signature": doc.keys_receiver_name,
				"client_signature": "Ada Client",
				"technician_signature": get_fullname(self.technician),
			},
		)
		snapshot = frappe.parse_json(doc.submission_snapshot)
		self.assertEqual(snapshot["values"]["ip_address"], doc.ip_address)
		self.assertEqual(snapshot["signatures"]["client_signature"]["signer_name"], "Ada Client")
		with set_user(self.technician), self.assertRaises(frappe.ValidationError):
			doc.remarks = "changed after submit"
			doc.save()

	def test_only_people_on_the_job_can_read_the_form(self):
		other = "_install-tech@deployops.test"
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


class TestReport(InstallationTestCase):
	def submitted(self):
		doc = self.completed()
		with set_user(self.technician):
			doc.set(
				"installation_photos",
				[{"image": real_photo(doc.name, shade)} for shade in (40, 80, 120)],
			)
			doc.ip_address = "192.0.2.10"
			doc.save()
			doc.submit()
		return self.doc()

	def test_report_has_every_section_from_the_snapshot(self):
		doc = self.submitted()
		frappe.db.set_value(FORM, doc.name, "ip_address", "changed later")  # bypasses the lock
		html = report.render_html(self.doc())
		self.assertIn("192.0.2.10", html)
		self.assertNotIn("changed later", html)
		for label in (*REQUIRED_STEPS, *AT_LEAST_ONE_STEPS, "Key handover confirmation", "POS integration"):
			with self.subTest(label=label):
				self.assertIn(label, html)
		self.assertEqual(
			html.count('class="tick done"'), sum(REQUIRED_STEPS.values()) + len(AT_LEAST_ONE_STEPS)
		)
		self.assertIn("data:image/jpeg;base64,", html)
		self.assertNotIn("/private/files/", html)

	def test_customer_copy_leaves_out_internal_details(self):
		doc = self.submitted()
		internal, customer = (report.render_html(doc, audience) for audience in ("internal", "customer"))
		for text in (doc.job, "Audit trail", "Form version"):
			with self.subTest(text=text):
				self.assertIn(text, internal)
				self.assertNotIn(text, customer)
		self.assertIn("JOB-CR-1", customer)

	def test_desk_print_formats_render_the_same_report(self):
		doc = self.submitted()
		for print_format, kind in (
			("Cashmatic Installation Report", "Internal report"),
			("Cashmatic Installation Report (Customer)", "Customer copy"),
		):
			with self.subTest(print_format=print_format):
				html = frappe.get_print(FORM, doc.name, print_format, doc=doc)
				self.assertIn(kind, html)
				self.assertIn("Cashmatic Installation", html)

	def test_the_app_offers_a_real_pdf_only_once_submitted(self):
		with set_user(self.technician):
			self.assertEqual(technician_api.form_view(FORM, self.name)["reports"], [])
			with self.assertRaisesRegex(frappe.ValidationError, "Only a submitted"):
				reports_api.checklist_pdf(FORM, self.name)
		self.submitted()
		frappe.local.response = frappe._dict()
		with set_user(self.technician):
			audiences = [r["audience"] for r in technician_api.form_view(FORM, self.name)["reports"]]
			reports_api.checklist_pdf(FORM, self.name, "customer")
		self.assertEqual(audiences, ["internal", "customer"])
		self.assertTrue(frappe.local.response.filecontent.startswith(b"%PDF"))
