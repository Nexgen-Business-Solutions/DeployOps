"""v2 Plan 3 Task 5: the machine forms API (list, start, override, discard, cancel)."""

import json
from unittest.mock import patch

import frappe
from forms_core import api
from forms_core.ids import new_id
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user
from frappe.tests.test_api import make_request
from frappe.utils import get_test_client, get_url

from deployops.api import forms as forms_api
from deployops.api import jobs as job_api
from deployops.forms import machine_forms
from deployops.roles import MANAGER, TECHNICIAN
from deployops.tests import erpnext_fixtures as fx
from deployops.tests.forms_utils import JOB, RULE, FormJobCase, add_rule, publish_job_form
from deployops.tests.test_forms_provider import make_user
from deployops.tests.test_job import make_job
from deployops.tests.utils import api_token, make_role_user

FORM_ROW = "DeployOps Job Device Form"
SUBMISSION = "Form Submission"
TITLE_A = "Job form job-form-a"
TITLE_B = "Job form job-form-b"
FORM_KEYS = {
	"form",
	"title",
	"subtitle",
	"icon",
	"color",
	"required",
	"origin",
	"status",
	"submission",
	"form_version",
	"flagged",
	"can_start",
	"can_remove",
	"remove_needs_manager",
}
TOP_KEYS = {
	"job",
	"row",
	"item_code",
	"serial_no",
	"device_status",
	"job_status",
	"frozen",
	"uses_forms",
	"forms",
	"can_add",
	"addable",
}


class TestFormsApi(FormJobCase):
	def setUp(self):
		super().setUp()
		self.manager = make_user(make_role_user(MANAGER), MANAGER)
		note = self.delivery_note(
			[{"item_code": self.cash, "serial_and_batch_bundle": fx.make_bundle(self.cash, ["JOB-CR-1"])}]
		)
		self.job = make_job("Delivery Note", note, assigned_technician=self.technician).name
		self.row = frappe.get_doc(JOB, self.job).devices[0].name
		with set_user(self.supervisor):
			job_api.job_action(self.job, "start")
		with set_user(self.technician):
			job_api.job_action(self.job, "arrive")
			job_api.device_action(self.job, self.row, "start")

	# -- helpers ------------------------------------------------------------------------------

	def listing(self, user=None) -> dict:
		with set_user(user or self.technician):
			return forms_api.machine_forms(self.job, self.row)

	def entry(self, form: dict, user=None) -> dict:
		return next(f for f in self.listing(user)["forms"] if f["form"] == form["form"])

	def start(self, form: dict, user=None) -> dict:
		with set_user(user or self.technician):
			return forms_api.start_machine_form(self.job, self.row, form["form"])

	def fill(self, name: str, form: dict, submit: bool = True):
		with set_user(self.technician):
			api.save_answers(name, {form["note"]: "Fitted", form["safe"]: "Yes"})
			if submit:
				api.submit(name)

	def override(self, user, **kwargs) -> dict:
		with set_user(user):
			return forms_api.override_machine_forms(self.job, self.row, **kwargs)

	def cancel(self, name: str, reason: str = "Wrong serial"):
		with set_user(self.manager):
			return forms_api.cancel_machine_form(name, reason)

	def rows(self) -> list[tuple]:
		job = frappe.get_doc(JOB, self.job)
		return [(r.form, r.origin, r.required, r.removed) for r in job.device_forms]

	def log(self) -> list[tuple]:
		return [(r.action, r.reason) for r in frappe.get_doc(JOB, self.job).status_log]

	# -- machine_forms ------------------------------------------------------------------------

	def test_machine_forms_shape_and_statuses(self):
		data = self.listing()
		self.assertEqual(set(data), TOP_KEYS)
		self.assertEqual(
			(data["job"], data["row"], data["item_code"], data["serial_no"]),
			(self.job, self.row, self.cash, "JOB-CR-1"),
		)
		self.assertEqual((data["device_status"], data["job_status"]), ("In Progress", "On Site"))
		self.assertEqual((data["frozen"], data["uses_forms"]), (False, True))
		self.assertEqual([f["form"] for f in data["forms"]], [self.form_a["form"], self.form_b["form"]])
		for entry in data["forms"]:
			self.assertEqual(set(entry), FORM_KEYS)
		first = data["forms"][0]
		self.assertEqual(
			{k: first[k] for k in ("title", "required", "origin", "status", "submission", "form_version")},
			{
				"title": TITLE_A,
				"required": True,
				"origin": "Rule",
				"status": "Not started",
				"submission": None,
				"form_version": None,
			},
		)
		self.assertTrue(first["can_start"])
		self.assertFalse(first["can_remove"])  # the technician is no approver
		self.assertTrue(first["remove_needs_manager"])
		self.assertFalse(data["forms"][1]["remove_needs_manager"])
		self.assertEqual((data["can_add"], data["addable"]), (False, []))

		name = self.start(self.form_a)["submission"]
		entry = self.entry(self.form_a)
		self.assertEqual((entry["status"], entry["submission"]), ("Draft", name))
		self.assertEqual(entry["form_version"], frappe.db.get_value(SUBMISSION, name, "form_version"))
		self.assertFalse(entry["can_start"])
		self.assertTrue(self.listing()["frozen"])

		self.fill(name, self.form_a)
		entry = self.entry(self.form_a)
		self.assertEqual(
			(entry["status"], entry["submission"], entry["can_start"]), ("Submitted", name, False)
		)

	def test_supervisor_sees_addable_forms(self):
		extra = publish_job_form("job-form-extra")
		data = self.listing(self.supervisor)
		self.assertTrue(data["can_add"])
		addable = [f["form"] for f in data["addable"]]
		self.assertIn(extra["form"], addable)
		self.assertNotIn(self.form_a["form"], addable)
		self.assertEqual(
			next(f for f in data["addable"] if f["form"] == extra["form"]),
			{"form": extra["form"], "title": "Job form job-form-extra"},
		)
		self.assertFalse(self.entry(self.form_a, self.supervisor)["can_start"])  # no c letter
		self.assertTrue(self.entry(self.form_b, self.supervisor)["can_remove"])
		self.assertFalse(self.entry(self.form_a, self.supervisor)["can_remove"])  # required: Manager
		self.assertTrue(self.entry(self.form_a, self.manager)["can_remove"])

	def test_outsider_cannot_list(self):
		other = make_user("_second-tech@deployops.test", TECHNICIAN)
		with set_user(other), self.assertRaises(frappe.PermissionError):
			forms_api.machine_forms(self.job, self.row)

	# -- start --------------------------------------------------------------------------------

	def test_start_returns_existing_draft(self):
		first = self.start(self.form_a)
		self.assertTrue(first["created"])
		self.assertEqual(self.start(self.form_a), {"submission": first["submission"], "created": False})
		self.assertEqual(
			frappe.db.count(SUBMISSION, {"context_name": self.job, "form": self.form_a["form"]}), 1
		)

	def test_restart_after_cancel_amends(self):
		name = self.start(self.form_a)["submission"]
		self.fill(name, self.form_a)
		self.assertEqual(self.cancel(name), 2)
		entry = self.entry(self.form_a)
		self.assertEqual(
			(entry["status"], entry["submission"], entry["can_start"]), ("Not started", name, True)
		)

		again = self.start(self.form_a)
		self.assertTrue(again["created"])
		self.assertEqual(frappe.db.get_value(SUBMISSION, again["submission"], "amended_from"), name)
		entry = self.entry(self.form_a)
		self.assertEqual((entry["status"], entry["submission"]), ("Draft", again["submission"]))

	# -- override -----------------------------------------------------------------------------

	def test_supervisor_adds_and_removes_optional_logged(self):
		extra = publish_job_form("job-form-extra")
		data = self.override(self.supervisor, add=json.dumps([extra["form"]]), remove=[self.form_b["form"]])
		self.assertEqual([f["form"] for f in data["forms"]], [self.form_a["form"], extra["form"]])
		self.assertEqual(
			self.rows(),
			[
				(self.form_a["form"], "Rule", 1, 0),
				(self.form_b["form"], "Rule", 0, 1),
				(extra["form"], "Override", 0, 0),
			],
		)
		log = self.log()
		self.assertIn(("forms: add", "Job form job-form-extra"), log)
		self.assertIn(("forms: remove", TITLE_B), log)

		# Adding a removed form back restores its row as an override.
		self.override(self.supervisor, add=[self.form_b["form"]], required=1)
		self.assertIn((self.form_b["form"], "Override", 1, 0), self.rows())
		with self.assertRaisesRegex(frappe.ValidationError, f"Form {TITLE_B} is already planned"):
			self.override(self.supervisor, add=[self.form_b["form"]])

	def test_supervisor_cannot_remove_required(self):
		with self.assertRaises(frappe.PermissionError):
			self.override(self.supervisor, remove=[self.form_a["form"]], reason="Not needed")
		self.assertIn((self.form_a["form"], "Rule", 1, 0), self.rows())

	def test_manager_removes_required_with_reason_only(self):
		with self.assertRaisesRegex(
			frappe.ValidationError, "A reason is required to remove a required form."
		):
			self.override(self.manager, remove=[self.form_a["form"]])
		self.assertIn((self.form_a["form"], "Rule", 1, 0), self.rows())
		self.override(self.manager, remove=[self.form_a["form"]], reason="Customer declined")
		self.assertIn((self.form_a["form"], "Rule", 1, 1), self.rows())
		self.assertIn(("forms: remove", f"{TITLE_A}: Customer declined"), self.log())

	def test_remove_refused_with_live_submission(self):
		self.start(self.form_b)
		with self.assertRaisesRegex(frappe.ValidationError, f"Cancel or discard form {TITLE_B} first."):
			self.override(self.supervisor, remove=[self.form_b["form"]])
		self.assertIn((self.form_b["form"], "Rule", 0, 0), self.rows())
		self.assertFalse(self.entry(self.form_b, self.supervisor)["can_remove"])

	def test_override_survives_rule_resync(self):
		extra = publish_job_form("job-form-extra")
		self.override(self.supervisor, add=[extra["form"]], remove=[self.form_b["form"]])
		machine_forms.resync_job_type("Installation")
		self.assertEqual(
			self.rows(),
			[
				(self.form_a["form"], "Rule", 1, 0),
				(self.form_b["form"], "Rule", 0, 1),
				(extra["form"], "Override", 0, 0),
			],
		)

	def test_override_all_or_nothing(self):
		extra = publish_job_form("job-form-extra")
		archived = publish_job_form("job-form-archived")
		frappe.db.set_value("Form", archived["form"], "status", "Archived")
		before = self.rows()
		with self.assertRaises(frappe.ValidationError):
			self.override(
				self.supervisor, add=[extra["form"], archived["form"]], remove=[self.form_b["form"]]
			)
		self.assertEqual(self.rows(), before)
		self.assertNotIn("forms: add", [action for action, _reason in self.log()])

		# A bad remove after valid adds changes nothing either.
		unplanned = publish_job_form("job-form-unplanned")
		with self.assertRaisesRegex(
			frappe.ValidationError, "Form Job form job-form-unplanned is not planned for this machine."
		):
			self.override(self.supervisor, add=[extra["form"]], remove=[unplanned["form"]])
		self.assertEqual(self.rows(), before)
		self.assertNotIn("forms: add", [action for action, _reason in self.log()])

	def test_override_refuses_bad_form_lists(self):
		for bad in ('{"a": 1}', "5", "not json", "[1]"):
			with self.assertRaisesRegex(frappe.ValidationError, "list of form names"):
				self.override(self.supervisor, add=bad)

	def test_add_refused_on_machine_with_v1_checklist(self):
		extra = publish_job_form("job-form-extra")
		with patch("deployops.forms.machine_forms.form_for_device", return_value=("X", "X-1", 0)):
			self.assertFalse(self.listing(self.supervisor)["can_add"])
			with self.assertRaisesRegex(frappe.ValidationError, "has a checklist"):
				self.override(self.supervisor, add=[extra["form"]])
		self.assertNotIn(extra["form"], [form for form, *_rest in self.rows()])

	def test_restore_keeps_cancelled_link_and_next_start_amends(self):
		name = self.start(self.form_b)["submission"]
		self.fill(name, self.form_b)
		self.cancel(name)
		self.override(self.supervisor, remove=[self.form_b["form"]])
		self.override(self.supervisor, add=[self.form_b["form"]])
		entry = self.entry(self.form_b)
		self.assertEqual((entry["status"], entry["submission"]), ("Not started", name))
		again = self.start(self.form_b)["submission"]
		self.assertEqual(frappe.db.get_value(SUBMISSION, again, "amended_from"), name)

	def test_override_refused_on_completed_machine(self):
		extra = publish_job_form("job-form-extra")
		frappe.db.set_value("DeployOps Job Device", self.row, "device_status", "Completed")
		with self.assertRaises(frappe.ValidationError):
			self.override(self.supervisor, add=[extra["form"]])
		self.assertFalse(self.listing(self.supervisor)["can_add"])

	def test_technician_cannot_override(self):
		extra = publish_job_form("job-form-extra")
		with self.assertRaises(frappe.PermissionError):
			self.override(self.technician, add=[extra["form"]])
		self.assertNotIn(extra["form"], [form for form, *_rest in self.rows()])

	# -- discard and cancel -------------------------------------------------------------------

	def test_discard_draft_manager_only_logged(self):
		name = self.start(self.form_b)["submission"]
		for user in (self.technician, self.supervisor):
			with set_user(user), self.assertRaises(frappe.PermissionError):
				forms_api.discard_machine_form(name, "Started by mistake")
		with set_user(self.manager):
			with self.assertRaisesRegex(frappe.ValidationError, "reason"):
				forms_api.discard_machine_form(name, " ")
			forms_api.discard_machine_form(name, "Started by mistake")
		self.assertFalse(frappe.db.exists(SUBMISSION, name))
		self.assertIn(("form: draft discarded", f"{TITLE_B} ({name}): Started by mistake"), self.log())
		entry = self.entry(self.form_b)
		self.assertEqual(
			(entry["status"], entry["submission"], entry["can_start"]), ("Not started", None, True)
		)

	def test_discard_amendment_relinks_cancelled_original(self):
		name = self.start(self.form_a)["submission"]
		self.fill(name, self.form_a)
		self.cancel(name)
		amendment = self.start(self.form_a)["submission"]
		with set_user(self.manager):
			forms_api.discard_machine_form(amendment, "Started by mistake")
		self.assertFalse(frappe.db.exists(SUBMISSION, amendment))
		entry = self.entry(self.form_a)
		self.assertEqual(
			(entry["status"], entry["submission"], entry["can_start"]), ("Not started", name, True)
		)
		again = self.start(self.form_a)["submission"]
		self.assertEqual(frappe.db.get_value(SUBMISSION, again, "amended_from"), name)

	def test_discard_refused_on_closed_job(self):
		name = self.start(self.form_b)["submission"]
		frappe.db.set_value(JOB, self.job, "status", "Cancelled")
		with set_user(self.manager), self.assertRaisesRegex(frappe.ValidationError, "Cancelled job"):
			forms_api.discard_machine_form(name, "Too late")
		self.assertTrue(frappe.db.exists(SUBMISSION, name))

	def test_discard_refused_on_submitted_form(self):
		name = self.start(self.form_a)["submission"]
		self.fill(name, self.form_a)
		with set_user(self.manager), self.assertRaises(frappe.ValidationError):
			forms_api.discard_machine_form(name, "Wrong")
		self.assertEqual(frappe.db.get_value(SUBMISSION, name, "docstatus"), 1)

	def test_cancel_requires_reason_and_manager(self):
		name = self.start(self.form_a)["submission"]
		self.fill(name, self.form_a)
		with set_user(self.manager), self.assertRaisesRegex(frappe.ValidationError, "reason"):
			forms_api.cancel_machine_form(name, "")
		for user in (self.technician, self.supervisor):
			with set_user(user), self.assertRaises(frappe.PermissionError):
				forms_api.cancel_machine_form(name, "Wrong serial")
		self.assertEqual(frappe.db.get_value(SUBMISSION, name, "docstatus"), 1)
		self.assertEqual(self.cancel(name, "Wrong serial"), 2)
		self.assertIsNone(frappe.flags.get("deployops_form_cancel"))
		self.assertIn(("form: cancelled", f"{TITLE_A}: Wrong serial"), self.log())


class TestFormsApiOverHttp(IntegrationTestCase):
	"""machine_forms and start_machine_form over real HTTP, as the assigned technician."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		fx.make_company()
		cls.item = fx.make_item("_Fa CR-460")
		cls.customer = fx.make_customer("_FaCust")
		# Clean up any open jobs left by a previous crashed run holding FA-SN-1.
		for job_name in frappe.db.sql(
			"SELECT DISTINCT parent FROM `tabDeployOps Job Device` WHERE serial_no = 'FA-SN-1'",
			pluck="parent",
		):
			if frappe.db.exists(JOB, job_name):
				frappe.db.delete(SUBMISSION, {"context_doctype": JOB, "context_name": job_name})
				frappe.delete_doc(JOB, job_name, force=True, ignore_permissions=True, ignore_on_trash=True)
		frappe.db.commit()  # nosemgrep
		if not frappe.db.exists("DeployOps Equipment Category", "_Fa Cash"):
			frappe.get_doc(
				{
					"doctype": "DeployOps Equipment Category",
					"category_name": "_Fa Cash",
					"items": [{"item_code": cls.item}],
				}
			).insert(ignore_permissions=True)
		cls.tech = "fa-tech@deployops.test"
		if not frappe.db.exists("User", cls.tech):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": cls.tech,
					"first_name": "fa-tech",
					"send_welcome_email": 0,
					"roles": [{"role": TECHNICIAN}],
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("DeployOps Equipment Access Profile", cls.tech):
			frappe.get_doc(
				{
					"doctype": "DeployOps Equipment Access Profile",
					"user": cls.tech,
					"categories": [{"category": "_Fa Cash"}],
				}
			).insert(ignore_permissions=True)
		cls.form = publish_job_form("fa-" + new_id("k")[2:])["form"]
		cls.rule = add_rule("Installation", "_Fa Cash", cls.form)
		fx.make_serial("FA-SN-1", cls.item)
		note = fx.make_delivery_note(cls.customer, [{"item_code": cls.item, "serial_no": "FA-SN-1"}]).name
		cls.job = (
			frappe.get_doc(
				{
					"doctype": JOB,
					"job_type": "Installation",
					"company": fx.COMPANY,
					"source_doctype": "Delivery Note",
					"source_name": note,
					"assigned_technician": cls.tech,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
		frappe.db.set_value(JOB, cls.job, "status", "On Site")
		cls.row = frappe.get_doc(JOB, cls.job).devices[0].name
		cls.token = api_token(cls.tech)
		# Requests run on a separate DB connection and only see committed data.
		frappe.db.commit()  # nosemgrep
		cls.client = get_test_client(use_cookies=False)

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		# Submissions, versions and forms refuse delete_doc once published; remove them directly.
		frappe.db.delete(SUBMISSION, {"context_doctype": JOB, "context_name": cls.job})
		frappe.db.delete(RULE, {"name": cls.rule})
		frappe.db.delete("Form Version", {"form": cls.form})
		frappe.db.delete("Form", {"name": cls.form})
		fx.purge(
			names={
				JOB: [cls.job],
				"DeployOps Equipment Access Profile": [cls.tech],
				"DeployOps Equipment Category": ["_Fa Cash"],
				"User": [cls.tech],
				"Customer": [cls.customer],
				"Item": [cls.item],
			}
		)
		# Remove the committed fixtures so no test data stays on the site.
		frappe.db.commit()  # nosemgrep
		super().tearDownClass()

	def call(self, http_method, method, data, who=True):
		url = get_url(f"/api/method/deployops.api.forms.{method}")
		kwargs = {"headers": {"Authorization": self.token}} if who else {}
		if http_method == "POST":
			kwargs["json"] = data
			target = self.client.post
		else:
			kwargs["query_string"] = data
			target = self.client.get
		return make_request(target=target, args=(url,), kwargs=kwargs)

	def test_api_over_http(self):
		where = {"job": self.job, "row": self.row}
		self.assertEqual(self.call("GET", "machine_forms", where, who=False).status_code, 403)
		response = self.call("GET", "machine_forms", where)
		self.assertEqual(response.status_code, 200, response.data[:300])
		data = json.loads(response.data)["message"]
		self.assertEqual(
			[(f["form"], f["status"], f["can_start"]) for f in data["forms"]],
			[(self.form, "Not started", True)],
		)

		start = {**where, "form": self.form}
		self.assertNotEqual(self.call("GET", "start_machine_form", start).status_code, 200)  # POST only
		response = self.call("POST", "start_machine_form", start)
		self.assertEqual(response.status_code, 200, response.data[:300])
		started = json.loads(response.data)["message"]
		self.assertTrue(started["created"])
		response = self.call("POST", "start_machine_form", start)
		self.assertEqual(json.loads(response.data)["message"], {**started, "created": False})

		data = json.loads(self.call("GET", "machine_forms", where).data)["message"]
		self.assertEqual(
			[(f["status"], f["submission"]) for f in data["forms"]], [("Draft", started["submission"])]
		)
