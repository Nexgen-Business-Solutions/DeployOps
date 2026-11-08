from unittest.mock import patch

import frappe
from forms_core import api
from forms_core.errors import FormValidationError
from frappe.tests.classes.context_managers import set_user

from deployops.forms.provider import JobFormProvider
from deployops.roles import ADMINISTRATOR, MANAGER, SUPERVISOR, TECHNICIAN
from deployops.tests import erpnext_fixtures as fx
from deployops.tests.forms_utils import JOB, FormJobCase, publish_job_form
from deployops.tests.test_forms_rules import make_category
from deployops.tests.test_job import make_job
from deployops.tests.utils import make_role_user

DEVICE = "DeployOps Job Device"
FORM_ROW = "DeployOps Job Device Form"
SUBMISSION = "Form Submission"


def make_user(email: str, role: str, categories=("_Test Cash",)) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"send_welcome_email": 0,
				"roles": [{"role": role}],
			}
		).insert(ignore_permissions=True)
	frappe.db.delete("DeployOps Equipment Access Profile Category", {"parent": email})
	frappe.db.delete("DeployOps Equipment Access Profile", {"name": email})
	frappe.get_doc(
		{
			"doctype": "DeployOps Equipment Access Profile",
			"user": email,
			"categories": [{"category": category} for category in categories],
		}
	).insert(ignore_permissions=True)
	return email


class TestJobFormProvider(FormJobCase):
	def setUp(self):
		super().setUp()
		self.provider = JobFormProvider()
		self.manager = make_user(make_role_user(MANAGER), MANAGER)
		self.admin = make_role_user(ADMINISTRATOR)
		note = self.delivery_note(
			[{"item_code": self.cash, "serial_and_batch_bundle": fx.make_bundle(self.cash, ["JOB-CR-1"])}]
		)
		self.job = make_job("Delivery Note", note, assigned_technician=self.technician).name
		self.device = frappe.get_doc(JOB, self.job).devices[0].name
		self.set_status("On Site")

	def set_status(self, status: str):
		frappe.db.set_value(JOB, self.job, "status", status)

	def start(self, user=None, form=None) -> str:
		with set_user(user or self.technician):
			return api.start_submission(form or self.form_a["form"], JOB, self.job, self.device)

	def can_start(self, form=None, job=None, device=None):
		return self.provider.can_start(job or self.job, device or self.device, form or self.form_a["form"])

	def test_assigned_technician_starts_saves_submits(self):
		name = self.start()
		form = self.form_a
		with set_user(self.technician):
			self.assertEqual(api.get_submission(name)["answers"][form["serial"]], "JOB-CR-1")
			with self.assertRaises(FormValidationError):
				api.save_answers(name, {form["serial"]: "OTHER"})
			answers = api.save_answers(name, {form["note"]: "Fitted", form["safe"]: "Yes"})
			self.assertEqual(answers[form["serial"]], "JOB-CR-1")
			api.submit(name)
		self.assertEqual(frappe.db.get_value(SUBMISSION, name, "docstatus"), 1)
		row = frappe.db.get_value(
			FORM_ROW, {"parent": self.job, "device": self.device, "form": form["form"]}, "submission"
		)
		self.assertEqual(row, name)

	def test_can_start_refusals(self):
		form_c = publish_job_form("job-form-c")["form"]
		self.assertEqual(self.can_start(job="DO-JOB-NOPE"), "This job does not exist.")
		self.set_status("Draft")
		self.assertEqual(self.can_start(), "A form can only be started while the job is being worked on.")
		self.set_status("Ready for Deployment")
		self.assertEqual(self.can_start(device="nothing"), f"That machine is not on job {self.job}.")
		frappe.db.set_value(DEVICE, self.device, "device_status", "Cancelled")
		self.assertEqual(self.can_start(), "This machine was cancelled on the job.")
		frappe.db.set_value(DEVICE, self.device, "device_status", "Pending")
		self.assertEqual(self.can_start(form=form_c), "This form is not planned for this machine.")
		self.start()
		self.assertEqual(self.can_start(), "This machine already has this form on this job.")
		self.assertIsNone(self.can_start(form=self.form_b["form"]))

	def test_second_start_refused(self):
		self.start()
		with self.assertRaisesRegex(frappe.ValidationError, "already has this form on this job"):
			self.start()
		self.assertEqual(
			frappe.db.count(SUBMISSION, {"context_name": self.job, "form": self.form_a["form"]}), 1
		)

	def test_can_start_locks_job_row(self):
		with patch("deployops.forms.provider.frappe.db.get_value", wraps=frappe.db.get_value) as get_value:
			self.assertIsNone(self.can_start())
		get_value.assert_any_call(JOB, self.job, "status", for_update=True)
		self.assertEqual(get_value.call_args_list[0].kwargs, {"for_update": True})

	def test_supervisor_reads_cannot_write_or_start(self):
		name = self.start()
		doc = frappe.get_doc(SUBMISSION, name)
		with set_user(self.supervisor):
			self.assertEqual(api.get_submission(name)["name"], name)
			with self.assertRaises(frappe.PermissionError):
				api.save_answers(name, {self.form_a["note"]: "x"})
			with self.assertRaises(frappe.PermissionError):
				api.start_submission(self.form_b["form"], JOB, self.job, self.device)
		self.assertTrue(self.provider.has_permission(doc, self.supervisor, "print"))
		self.assertFalse(self.provider.has_permission(doc, self.supervisor, "submit"))
		self.assertFalse(self.provider.has_permission(doc, self.supervisor, "export"))

	def test_manager_reads_cannot_cancel_directly(self):
		name = self.start()
		with set_user(self.technician):
			api.save_answers(name, {self.form_a["note"]: "Fitted", self.form_a["safe"]: "Yes"})
			api.submit(name)
		doc = frappe.get_doc(SUBMISSION, name)
		with set_user(self.manager):
			self.assertEqual(api.get_submission(name)["name"], name)
			with self.assertRaises(frappe.PermissionError):
				api.cancel(name)
		self.assertEqual(frappe.db.get_value(SUBMISSION, name, "docstatus"), 1)
		self.assertFalse(self.provider.has_permission(doc, self.manager, "write"))
		self.assertTrue(self.provider.has_permission(doc, self.manager, "export"))
		frappe.flags.deployops_form_cancel = True
		self.addCleanup(frappe.flags.pop, "deployops_form_cancel", None)
		self.assertTrue(self.provider.has_permission(doc, self.manager, "cancel"))
		self.assertFalse(self.provider.has_permission(doc, self.technician, "cancel"))
		self.set_status("Completed")
		self.assertFalse(self.provider.has_permission(doc, self.manager, "cancel"))

	def test_unassigned_technician_cannot_write(self):
		name = self.start()
		other = make_user("_second-tech@deployops.test", TECHNICIAN)
		doc = frappe.get_doc(SUBMISSION, name)
		for ptype in ("read", "create", "write", "submit"):
			self.assertFalse(self.provider.has_permission(doc, other, ptype), ptype)
		# Even once the job is in their scope, only the assignee creates, writes and submits.
		with patch("deployops.forms.provider.job_in_scope", return_value=True):
			self.assertTrue(self.provider.has_permission(doc, other, "read"))
			for ptype in ("create", "write", "submit"):
				self.assertFalse(self.provider.has_permission(doc, other, ptype), ptype)
		self.assertTrue(self.provider.has_permission(doc, self.technician, "write"))
		self.assertFalse(self.provider.has_permission(doc, self.technician, "delete"))

	def test_outsider_refused_through_forms_core_api(self):
		name = self.start()
		outsider = make_user("_outsider-tech@deployops.test", TECHNICIAN)
		with set_user(outsider):
			with self.assertRaises(frappe.PermissionError):
				api.get_submission(name)
			with self.assertRaises(frappe.PermissionError):
				api.start_submission(self.form_b["form"], JOB, self.job, self.device)
			with self.assertRaises(frappe.PermissionError):
				api.save_answers(name, {self.form_a["note"]: "x"})
			self.assertNotIn(name, frappe.get_list(SUBMISSION, pluck="name"))
		with set_user(self.technician):
			self.assertIn(name, frappe.get_list(SUBMISSION, pluck="name"))

	def test_query_conditions_follow_job_visibility(self):
		name = self.start()
		make_category("_Test Robots", [self.robot])
		blind = make_user("_blind-supervisor@deployops.test", SUPERVISOR, categories=("_Test Robots",))
		for user, sees in ((self.supervisor, True), (blind, False), (self.admin, True)):
			with self.subTest(user=user), set_user(user):
				self.assertEqual(name in frappe.get_list(SUBMISSION, pluck="name"), sees)
		self.assertEqual(self.provider.query_conditions(self.admin), "1=1")
		self.assertIn("`tabForm Submission`.`context_name` in (", self.provider.query_conditions(blind))

	def test_attached_file_follows_job(self):
		name = self.start()
		outsider = make_user("_outsider-tech@deployops.test", TECHNICIAN)
		with set_user("Administrator"):
			file_doc = frappe.get_doc(
				{
					"doctype": "File",
					"file_name": "photo.txt",
					"content": b"evidence",
					"is_private": 1,
					"attached_to_doctype": SUBMISSION,
					"attached_to_name": name,
				}
			).insert(ignore_permissions=True)
		self.assertTrue(frappe.has_permission("File", "read", file_doc, user=self.technician))
		self.assertFalse(frappe.has_permission("File", "read", file_doc, user=outsider))

	def test_write_refused_once_job_pending_review(self):
		name = self.start()
		self.set_status("Pending Review")
		with set_user(self.technician):
			with self.assertRaises(frappe.PermissionError):
				api.save_answers(name, {self.form_a["note"]: "late"})
			self.assertEqual(api.get_submission(name)["name"], name)
