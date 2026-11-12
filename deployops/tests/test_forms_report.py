import frappe
from forms_core import api
from frappe.tests.classes.context_managers import set_user

from deployops.api import forms as forms_api
from deployops.api import jobs as job_api
from deployops.forms import report
from deployops.roles import TECHNICIAN
from deployops.tests import erpnext_fixtures as fx
from deployops.tests.forms_utils import JOB, FormJobCase
from deployops.tests.test_job import make_job

SUBMISSION = "Form Submission"


class TestFormsReport(FormJobCase):
	def submitted(self, submit=True):
		rows = [{"item_code": self.cash, "serial_and_batch_bundle": fx.make_bundle(self.cash, ["JOB-CR-1"])}]
		job = make_job("Delivery Note", self.delivery_note(rows), assigned_technician=self.technician).name
		with set_user(self.supervisor):
			job_api.job_action(job, "start")
		row = frappe.get_doc(JOB, job).devices[0].name
		form = self.form_a
		with set_user(self.technician):
			name = api.start_submission(form["form"], JOB, job, row)
			api.save_answers(name, {form["note"]: "Fitted <b>ok</b>", form["safe"]: "Yes"})
			if submit:
				api.submit(name)
		return job, name

	def test_internal_report_has_answers_job_and_audit(self):
		job, name = self.submitted()
		html = report.render_html(frappe.get_doc(SUBMISSION, name))
		for text in ("Fitted &lt;b&gt;ok&lt;/b&gt;", "JOB-CR-1", name, job, "Audit trail", "Internal report"):
			self.assertIn(text, html)

	def test_customer_copy_leaves_out_internal_details(self):
		job, name = self.submitted()
		html = report.render_html(frappe.get_doc(SUBMISSION, name), "customer")
		self.assertIn("Customer copy", html)
		self.assertIn("JOB-CR-1", html)
		self.assertNotIn(job, html)
		self.assertNotIn("Audit trail", html)

	def test_internal_only_fields_are_left_out_of_the_customer_copy(self):
		_job, name = self.submitted()
		doc = frappe.get_doc(SUBMISSION, name)
		fields = [{"id": "f_aaaaaa", "key": "cost", "type": "text", "label": "Our cost", "internal_only": True}]
		answers = {"f_aaaaaa": "120"}
		self.assertEqual(report._blocks(doc, fields, answers, internal=True)[0]["text"], "120")
		self.assertEqual(report._blocks(doc, fields, answers, internal=False), [])

	def test_multi_check_lists_every_option(self):
		_job, name = self.submitted()
		doc = frappe.get_doc(SUBMISSION, name)
		field = {"id": "f_bbbbbb", "key": "steps", "type": "multi_check", "label": "Steps", "config": {"options": ["A", "B"], "allow_other": True}}
		blocks = report._blocks(doc, [field], {"f_bbbbbb": {"selected": ["A"], "other": "C"}}, internal=True)
		self.assertEqual(blocks[0]["text"], "2 of 3 ticked")
		self.assertEqual([(s["label"], s["done"]) for s in blocks[1]["steps"]], [("A", True), ("B", False), ("Other: C", True)])

	def test_only_submitted_entries_have_a_report(self):
		_job, name = self.submitted(submit=False)
		with self.assertRaises(frappe.ValidationError):
			report.render_html(frappe.get_doc(SUBMISSION, name))

	def test_pdf_download_needs_read_access(self):
		_job, name = self.submitted()
		with set_user(self.technician):
			forms_api.submission_pdf(name)
			self.assertTrue(frappe.local.response.filecontent.startswith(b"%PDF"))
			self.assertTrue(frappe.db.exists("Access Log", {"reference_document": name}))
		other = "report.other.tech@example.com"
		if not frappe.db.exists("User", other):
			frappe.get_doc({"doctype": "User", "email": other, "first_name": "Other", "send_welcome_email": 0,
				"roles": [{"role": TECHNICIAN}]}).insert(ignore_permissions=True)
		with set_user(other), self.assertRaises(frappe.PermissionError):
			forms_api.submission_pdf(name, "customer")
