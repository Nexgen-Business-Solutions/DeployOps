"""Checklist reports (#27): built from the submitted snapshot, embedded evidence, two audiences,
escaped text, and the same access as printing the form."""

import io

import frappe
from frappe.tests.classes.context_managers import set_user
from frappe.tests.test_api import make_request
from frappe.utils import get_test_client, get_url

from deployops.api import reports as reports_api
from deployops.api import technician as technician_api
from deployops.checklists import report
from deployops.tests.test_cashmatic_preinstallation import FORM, SOURCE_STEPS, PreinstallationTestCase
from deployops.tests.test_job import JOB


def png() -> bytes:
	from PIL import Image

	buffer = io.BytesIO()
	Image.new("RGB", (1600, 900), (40, 120, 200)).save(buffer, "PNG")
	return buffer.getvalue()


class ReportTestCase(PreinstallationTestCase):
	def submitted(self, **values):
		doc = self.completed()
		photo = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"{frappe.generate_hash(length=8)}.png",
				"is_private": 1,
				"content": png(),
				"attached_to_doctype": FORM,
				"attached_to_name": doc.name,
			}
		).insert(ignore_permissions=True)
		with set_user(self.technician):
			doc.set("preparation_photos", [{"image": photo.file_url, "caption": "Wrapped"}])
			doc.update(values)
			doc.save()
			doc.submit()
		return frappe.get_doc(FORM, doc.name)


class TestReportContent(ReportTestCase):
	def test_built_from_the_snapshot_with_every_step(self):
		doc = self.submitted(software_version="SW 3.2.1")
		frappe.db.set_value(FORM, doc.name, "software_version", "changed later")  # bypasses the lock
		html = report.render_html(frappe.get_doc(FORM, doc.name))
		self.assertIn("SW 3.2.1", html)
		self.assertNotIn("changed later", html)
		self.assertEqual(html.count('class="tick done"'), sum(SOURCE_STEPS.values()))
		for label in ("Machine details", "Customer working hours", "Employee signature", "Monday"):
			self.assertIn(label, html)

	def test_photos_signature_and_logo_are_embedded_and_nothing_links_out(self):
		doc = self.submitted()
		html = report.render_html(doc)
		self.assertIn("data:image/jpeg;base64,", html)  # the photo, resized
		self.assertIn(doc.employee_signature, html)
		self.assertIn("data:image/png;base64,", html)  # the logo
		self.assertNotIn("/private/files/", html)
		self.assertNotIn("/files/", html)

	def test_customer_copy_leaves_out_internal_details(self):
		doc = self.submitted()
		internal, customer = (report.render_html(doc, audience) for audience in ("internal", "customer"))
		for text in (doc.job, "Audit trail", "Form version", "checklist: submit"):
			with self.subTest(text=text):
				self.assertIn(text, internal)
				self.assertNotIn(text, customer)
		self.assertIn("Customer copy", customer)
		self.assertIn("JOB-CR-1", customer)  # the answers and the machine stay

	def test_audit_trail_lists_the_job_and_this_machine_in_order(self):
		doc = self.submitted()
		actions = [entry["action"] for entry in report.context(doc)["audit"]]
		self.assertEqual(actions[0], "start")
		self.assertIn("checklist: submit", actions)

	def test_text_is_escaped(self):
		"""Stored text is sanitised HTML; the report shows plain text, escaped once."""
		doc = self.submitted(additional_remarks="<script>alert(1)</script>Tom & Jerry <b>bold</b> 1 < 2")
		html = report.render_html(doc)
		self.assertIn("Tom &amp; Jerry bold 1 &lt; 2", html)
		self.assertNotIn("<script", html)
		self.assertNotIn("&amp;amp;", html)

	def test_only_a_submitted_checklist_and_known_audience(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Only a submitted"):
			report.render_html(self.doc())
		doc = self.submitted()
		with self.assertRaisesRegex(frappe.ValidationError, "Unknown report audience"):
			report.render_html(doc, "everyone")

	def test_pdf_is_a_real_document(self):
		from pypdf import PdfReader

		pdf = report.render_pdf(self.submitted(software_version="SW 3.2.1"), "customer")
		text = "".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
		self.assertTrue(pdf.startswith(b"%PDF"))
		self.assertIn("SW 3.2.1", text)
		self.assertIn("Customer copy", text)

	def test_desk_print_formats_render_the_same_report(self):
		doc = self.submitted()
		for print_format, kind in (
			("Cashmatic Pre-installation Report", "Internal report"),
			("Cashmatic Pre-installation Report (Customer)", "Customer copy"),
		):
			with self.subTest(print_format=print_format):
				html = frappe.get_print(FORM, doc.name, print_format, doc=doc)
				self.assertIn(kind, html)
				self.assertIn("Cashmatic Pre-installation", html)


class TestReportAccess(ReportTestCase):
	def download(self, user, name, audience="internal"):
		frappe.local.response = frappe._dict()
		with set_user(user):
			reports_api.checklist_pdf(FORM, name, audience)
		return frappe.local.response

	def test_download_follows_who_may_print_the_form_and_is_logged(self):
		name = self.submitted().name
		for user in (self.technician, self.supervisor, self.manager):
			with self.subTest(user=user):
				response = self.download(user, name)
				self.assertEqual((response.type, response.filename), ("pdf", f"{name}.pdf"))
				self.assertTrue(response.filecontent.startswith(b"%PDF"))
		self.assertTrue(frappe.db.exists("Access Log", {"reference_document": name, "file_type": "PDF"}))

		other = "_report-tech@deployops.test"
		frappe.get_doc(
			{
				"doctype": "User",
				"email": other,
				"first_name": "Other",
				"send_welcome_email": 0,
				"roles": [{"role": "DeployOps Technician"}],
			}
		).insert(ignore_permissions=True)
		with self.assertRaises(frappe.PermissionError):
			self.download(other, name)  # a technician not on this job
		self.assertFalse(frappe.has_permission(FORM, "print", name, user=other))

	def test_form_view_offers_reports_once_submitted(self):
		with set_user(self.technician):
			self.assertEqual(technician_api.form_view(FORM, self.name)["reports"], [])
		self.submitted()
		with set_user(self.technician):
			reports = technician_api.form_view(FORM, self.name)["reports"]
		self.assertEqual([r["audience"] for r in reports], ["internal", "customer"])
		self.assertIn("deployops.api.reports.checklist_pdf", reports[0]["url"])

	def test_guests_are_refused_over_http(self):
		url = get_url("/api/method/deployops.api.reports.checklist_pdf")
		response = make_request(
			target=get_test_client(use_cookies=False).get,
			args=(url,),
			kwargs={"query_string": {"doctype": FORM, "name": self.name}},
		)
		self.assertEqual(response.status_code, 403)

	def test_a_draft_job_machine_has_no_report_even_for_a_manager(self):
		with set_user(self.manager), self.assertRaisesRegex(frappe.ValidationError, "Only a submitted"):
			reports_api.checklist_pdf(FORM, self.name)
		self.assertTrue(frappe.db.exists(JOB, self.job))
