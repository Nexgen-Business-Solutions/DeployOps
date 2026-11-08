"""v2 Plan 3 Task 6: form cards, a form's job list and the Supervisor report."""

import json

import frappe
from forms_core import api, versions
from forms_core.ids import new_id
from forms_core.reports import schema
from frappe.tests.classes.context_managers import set_user

from deployops.api import forms as forms_api
from deployops.api import jobs as job_api
from deployops.roles import MANAGER, SUPERVISOR, TECHNICIAN
from deployops.tests import erpnext_fixtures as fx
from deployops.tests.forms_utils import JOB, RULE, add_rule, publish_job_form
from deployops.tests.test_forms_provider import make_user
from deployops.tests.test_job import JobTestCase, make_job
from deployops.tests.utils import make_role_user

SUBMISSION = "Form Submission"
CARD_KEYS = {
	"form",
	"title",
	"subtitle",
	"icon",
	"color",
	"job_types",
	"open_jobs",
	"outstanding",
	"flagged",
	"attention",
	"waiting",
}
JOB_KEYS = {
	"name",
	"job_type",
	"customer_name",
	"address_display",
	"planned_date",
	"status",
	"machines",
	"outstanding",
	"flagged",
}
REPORT_PREFIX = "cards-rpt-"


class JobsMixin:
	"""Working Installation jobs on "_Test Cash" machines, and their forms filled in."""

	def working_job(self, serials: tuple[str, ...], technician: str | None = None) -> str:
		"""An Installation job On Site with every machine In Progress."""
		technician = technician or self.technician
		rows = [{"item_code": self.cash, "serial_and_batch_bundle": fx.make_bundle(self.cash, list(serials))}]
		job = make_job("Delivery Note", self.delivery_note(rows), assigned_technician=technician).name
		with set_user(self.supervisor):
			job_api.job_action(job, "start")
		with set_user(technician):
			job_api.job_action(job, "arrive")
			for device in self.devices(job):
				job_api.device_action(job, device, "start")
		return job

	def devices(self, job: str) -> list[str]:
		return [d.name for d in frappe.get_doc(JOB, job).devices]

	def fill(self, job: str, device: str, form: dict, safe="Yes", submit=True, user=None) -> str:
		"""Start the form on the machine as `user` (the job's technician by default), answer it and
		submit it."""
		with set_user(user or frappe.db.get_value(JOB, job, "assigned_technician")):
			name = api.start_submission(form["form"], JOB, job, device)
			api.save_answers(name, {form["note"]: "Fitted", form["safe"]: safe})
			if submit:
				api.submit(name)
		return name


class TestFormCards(JobsMixin, JobTestCase):
	def setUp(self):
		super().setUp()
		self.form_a = publish_job_form(outcome="flag_for_review")
		self.form_b = publish_job_form(outcome="flag_for_review")
		add_rule("Installation", "_Test Cash", self.form_a["form"], required=True, sort_order=0)
		add_rule("Installation", "_Test Cash", self.form_b["form"], required=False, sort_order=1)

	def cards(self, user=None) -> dict[str, dict]:
		with set_user(user or self.supervisor):
			return {card["form"]: card for card in forms_api.form_cards()}

	def counts(self, card: dict) -> tuple:
		return (card["open_jobs"], card["outstanding"], card["flagged"], card["attention"], card["waiting"])

	def test_cards_from_rules_only(self):
		no_rule = publish_job_form()
		archived = publish_job_form()
		add_rule("Installation", "_Test Cash", archived["form"], sort_order=2)
		frappe.db.set_value("Form", archived["form"], "status", "Archived")
		inactive = publish_job_form()
		frappe.db.set_value(
			RULE, add_rule("Installation", "_Test Cash", inactive["form"], sort_order=3), "active", 0
		)

		listed = [card["form"] for card in self.cards().values()]
		self.assertNotIn(no_rule["form"], listed)
		self.assertNotIn(archived["form"], listed)
		self.assertNotIn(inactive["form"], listed)
		self.assertLess(listed.index(self.form_a["form"]), listed.index(self.form_b["form"]))
		card = self.cards()[self.form_a["form"]]
		self.assertEqual(set(card), CARD_KEYS)
		self.assertEqual(card["title"], frappe.db.get_value("Form", self.form_a["form"], "title"))
		self.assertEqual(card["job_types"], ["Installation"])
		self.assertEqual(self.counts(card), (0, 0, 0, 0, False))

	def test_card_counts(self):
		done = self.working_job(("JOB-CR-1", "JOB-CR-2"))
		for device in self.devices(done):
			self.fill(done, device, self.form_a)
		waiting = self.working_job(("JOB-CR-3", "JOB-CR-4"))
		first, second = self.devices(waiting)
		self.fill(waiting, second, self.form_a, safe="No")  # A flagged on one machine, missing on the other
		self.fill(waiting, first, self.form_b, safe="No")  # optional B flagged

		cards = self.cards()
		self.assertEqual(self.counts(cards[self.form_a["form"]]), (2, 1, 1, 1, True))
		self.assertEqual(self.counts(cards[self.form_b["form"]]), (2, 0, 1, 1, True))

	def test_cards_follow_visibility(self):
		mine = self.working_job(("JOB-CR-1",))
		other = make_user("cards-other-tech@deployops.test", TECHNICIAN)
		self.working_job(("JOB-CR-2",), technician=other)
		self.assertEqual(self.cards(self.supervisor)[self.form_a["form"]]["open_jobs"], 2)
		self.assertEqual(self.cards(self.technician)[self.form_a["form"]]["open_jobs"], 1)
		with set_user(self.technician):
			jobs = forms_api.form_jobs(self.form_a["form"])["jobs"]
		self.assertEqual([j["name"] for j in jobs], [mine])
		outsider = make_user("cards-no-category@deployops.test", SUPERVISOR, categories=())
		self.assertEqual(self.cards(outsider)[self.form_a["form"]]["open_jobs"], 0)

	def test_cancelled_machine_not_counted(self):
		job = self.working_job(("JOB-CR-1", "JOB-CR-2"))
		first, second = self.devices(job)
		self.fill(job, first, self.form_a)
		self.assertEqual(self.counts(self.cards()[self.form_a["form"]]), (1, 1, 0, 1, True))
		with set_user(self.supervisor):
			job_api.device_action(job, second, "cancel", reason="Not delivered")
		self.assertEqual(self.counts(self.cards()[self.form_a["form"]]), (1, 0, 0, 0, False))

		with set_user(self.supervisor):
			job_api.device_action(job, first, "cancel", reason="Not delivered")
		self.assertEqual(self.cards()[self.form_a["form"]]["open_jobs"], 0)

	def test_form_jobs_shape(self):
		late = self.working_job(("JOB-CR-1", "JOB-CR-2"))
		early = self.working_job(("JOB-CR-3",))
		frappe.db.set_value(JOB, late, "planned_date", "2030-01-02")
		frappe.db.set_value(JOB, early, "planned_date", "2030-01-01")
		first = self.devices(late)[0]
		self.fill(late, first, self.form_a, safe="No")

		with set_user(self.supervisor):
			data = forms_api.form_jobs(self.form_a["form"])
		self.assertEqual(set(data), {"card", "jobs"})
		self.assertEqual(data["card"], self.cards()[self.form_a["form"]])
		ours = [j for j in data["jobs"] if j["name"] in (late, early)]
		self.assertEqual([j["name"] for j in ours], [early, late])
		for entry in ours:
			self.assertEqual(set(entry), JOB_KEYS)
		late_entry = ours[1]
		self.assertEqual(
			{k: late_entry[k] for k in ("job_type", "status", "machines", "outstanding", "flagged")},
			{"job_type": "Installation", "status": "On Site", "machines": 2, "outstanding": 1, "flagged": 1},
		)
		self.assertEqual(str(late_entry["planned_date"]), "2030-01-02")
		self.assertEqual(late_entry["customer_name"], frappe.db.get_value(JOB, late, "customer_name"))
		self.assertEqual((ours[0]["machines"], ours[0]["outstanding"], ours[0]["flagged"]), (1, 1, 0))

		no_rule = publish_job_form()
		with set_user(self.supervisor), self.assertRaises(frappe.DoesNotExistError):
			forms_api.form_jobs(no_rule["form"])


def report_definition() -> tuple[dict, dict]:
	"""A job form with a note, a yes/no, an old field (removed in v2) and a table."""
	ids = {k: new_id("f") for k in ("note", "safe", "old", "table", "col")}
	fields = [
		{"id": ids["note"], "key": "note", "type": "text", "label": "Note"},
		{"id": ids["safe"], "key": "safe", "type": "yes_no", "label": "Safe"},
		{"id": ids["old"], "key": "old", "type": "text", "label": "Old"},
		{
			"id": ids["table"],
			"key": "parts",
			"type": "table",
			"label": "Parts",
			"config": {"columns": [{"id": ids["col"], "type": "text", "label": "Part"}]},
		},
	]
	return {"schema": 1, "sections": [{"id": new_id("s"), "title": "Checks", "fields": fields}]}, ids


class TestReportRows(JobsMixin, JobTestCase):
	"""The report is built once (its DDL commits) and dropped at the end; each test rolls back."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		definition, cls.ids = report_definition()
		key = REPORT_PREFIX + frappe.generate_hash(length=8).lower()
		frappe.flags.forms_core_report_jobs = True
		try:
			form = frappe.get_doc(
				{
					"doctype": "Form",
					"title": f"Report form {key}",
					"key": key,
					"context_doctype": JOB,
					"draft_definition": json.dumps(definition),
				}
			).insert()
			cls.form_name = form.name
			versions.publish(form.name)
			fields = definition["sections"][0]["fields"]
			definition["sections"][0]["fields"] = [f for f in fields if f["id"] != cls.ids["old"]]
			form.reload()
			form.draft_definition = json.dumps(definition)
			form.save()
			versions.publish(form.name)
			schema.sync_schema(form.name)
		finally:
			frappe.flags.pop("forms_core_report_jobs", None)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit - the report DDL has committed already

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()
		schema.drop_report(cls.form_name)
		frappe.db.delete(RULE, {"form": cls.form_name})
		frappe.db.delete("Form Version", {"form": cls.form_name})
		frappe.db.delete("Form", {"name": cls.form_name})
		frappe.db.commit()  # nosemgrep: frappe-manual-commit - remove the committed report form
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		frappe.flags.forms_core_report_jobs = True
		self.addCleanup(frappe.flags.pop, "forms_core_report_jobs", None)
		self.addCleanup(frappe.flags.pop, "deployops_form_cancel", None)
		self.form = {"form": self.form_name, "note": self.ids["note"], "safe": self.ids["safe"]}
		add_rule("Installation", "_Test Cash", self.form_name)
		self.manager = make_user(make_role_user(MANAGER), MANAGER)

	def report(self, user=None, **kwargs) -> dict:
		with set_user(user or self.supervisor):
			return forms_api.report_rows(self.form_name, **kwargs)

	def submitted(self, serial: str, technician: str | None = None) -> tuple[str, str]:
		job = self.working_job((serial,), technician=technician)
		return job, self.fill(job, self.devices(job)[0], self.form)

	def test_supervisor_sees_only_visible_jobs_rows(self):
		job, mine = self.submitted("JOB-CR-1")
		# A job the Supervisor cannot see: one of its machines is outside their equipment.
		hidden = self.working_job(("JOB-CR-2",))
		frappe.get_doc(
			{
				"doctype": "DeployOps Job Device",
				"parent": hidden,
				"parenttype": JOB,
				"parentfield": "devices",
				"idx": 2,
				"item_code": self.robot,
				"serial_no": "JOB-BB-1",
				"device_status": "Pending",
			}
		).db_insert()
		unseen = self.fill(hidden, self.devices(hidden)[0], self.form, user="Administrator")

		data = self.report()
		self.assertEqual(set(data), {"status", "columns", "rows", "total", "start", "page_length"})
		self.assertEqual(data["status"], "OK")
		self.assertEqual([r["name"] for r in data["rows"]], [mine])
		self.assertEqual(data["total"], 1)
		self.assertEqual((data["start"], data["page_length"]), (0, 50))
		row = data["rows"][0]
		self.assertEqual((row["submission"], row["context_name"], row["status"]), (mine, job, "Submitted"))
		self.assertEqual(row[self.ids["note"]], "Fitted")
		self.assertEqual([r["name"] for r in self.report(self.manager)["rows"]], [mine])
		everyone = self.report("Administrator")
		self.assertEqual({r["name"] for r in everyone["rows"]}, {mine, unseen})
		self.assertEqual(everyone["total"], 2)

	def test_job_filter(self):
		first, one = self.submitted("JOB-CR-1")
		_second, two = self.submitted("JOB-CR-2")
		self.assertEqual({r["name"] for r in self.report()["rows"]}, {one, two})
		data = self.report(job=first)
		self.assertEqual(([r["name"] for r in data["rows"]], data["total"]), ([one], 1))
		paged = self.report(start=1, page_length=1)
		self.assertEqual((len(paged["rows"]), paged["total"], paged["start"]), (1, 2, 1))
		self.assertEqual(self.report(page_length=1000)["page_length"], 200)

	def test_technician_refused(self):
		self.submitted("JOB-CR-1")
		with self.assertRaises(frappe.PermissionError):
			self.report(self.technician)
		not_a_job_form = frappe.get_doc(
			{"doctype": "Form", "title": "Loose form", "key": "loose-" + new_id("k")[2:].lower()}
		).insert(ignore_permissions=True)
		with set_user(self.supervisor), self.assertRaises(frappe.DoesNotExistError):
			forms_api.report_rows(not_a_job_form.name)

	def test_drafts_excluded_cancelled_included(self):
		_job, kept = self.submitted("JOB-CR-1")
		_job, cancelled = self.submitted("JOB-CR-2")
		draft_job = self.working_job(("JOB-CR-3",))
		self.fill(draft_job, self.devices(draft_job)[0], self.form, submit=False)
		with set_user(self.manager):
			forms_api.cancel_machine_form(cancelled, "Wrong serial")

		rows = {r["name"]: r["status"] for r in self.report()["rows"]}
		self.assertEqual(rows, {kept: "Submitted", cancelled: "Cancelled"})

	def test_columns_skip_hidden_and_tables(self):
		self.submitted("JOB-CR-1")
		columns = self.report()["columns"]
		names = [c["fieldname"] for c in columns]
		self.assertEqual(names[: len(schema.PART_1_BUILT_INS)], [b[0] for b in schema.PART_1_BUILT_INS])
		self.assertNotIn(self.ids["old"], names)  # removed in v2, so hidden
		self.assertTrue(all(c["fieldtype"] != "Table" for c in columns))
		self.assertEqual(len(names), len(set(names)))
		for column in columns:
			self.assertEqual(set(column), {"fieldname", "label", "fieldtype"})
		self.assertIn(self.ids["note"], names)
		meta = frappe.get_meta(self.report_doctype())
		self.assertIn("Table", [f.fieldtype for f in meta.fields])  # the report has a table, left out
		self.assertTrue(meta.get_field(self.ids["old"]).hidden)

	def report_doctype(self) -> str:
		return schema.report_doctypes(self.form_name)["parts"][0]
