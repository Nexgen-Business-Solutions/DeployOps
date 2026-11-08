import frappe
from forms_core import context, permissions
from forms_core.errors import FormValidationError
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user

from deployops.forms import rules
from deployops.forms.provider import JobFormProvider
from deployops.roles import ADMINISTRATOR, MANAGER, SUPERVISOR, TECHNICIAN
from deployops.tests import erpnext_fixtures as fx
from deployops.tests.forms_utils import RULE, FormJobCase, add_rule, publish_job_form
from deployops.tests.test_job import JobTestCase, make_job
from deployops.tests.utils import make_role_user


def make_category(name: str, items: list[str], enabled: int = 1) -> str:
	frappe.db.delete("DeployOps Equipment Category Item", {"parent": name})
	frappe.db.delete("DeployOps Equipment Category", {"name": name})
	frappe.get_doc(
		{
			"doctype": "DeployOps Equipment Category",
			"category_name": name,
			"enabled": enabled,
			"items": [{"item_code": item} for item in items],
		}
	).insert(ignore_permissions=True)
	return name


def row(form, origin="Rule", required=1, sort_order=0, removed=0, submission=None, flagged=0, device="D1"):
	return {
		"device": device,
		"form": form,
		"required": required,
		"sort_order": sort_order,
		"origin": origin,
		"removed": removed,
		"submission": submission,
		"flagged": flagged,
	}


class TestFormsWiring(IntegrationTestCase):
	def setUp(self):
		self.addCleanup(frappe.db.rollback)

	def test_hooks_registered(self):
		self.assertEqual(frappe.get_hooks("forms_core_designer_roles"), [MANAGER, ADMINISTRATOR])
		self.assertIsInstance(context.get_provider("DeployOps Job"), JobFormProvider)
		self.assertIn("forms_core", frappe.get_hooks("required_apps"))

	def test_manager_is_designer_technician_not(self):
		for role, designer in (
			(MANAGER, True),
			(ADMINISTRATOR, True),
			(TECHNICIAN, False),
			(SUPERVISOR, False),
		):
			with self.subTest(role=role):
				self.assertEqual(permissions.is_designer(make_role_user(role)), designer)

	def test_publish_refuses_unknown_effect(self):
		with self.assertRaises(FormValidationError):
			publish_job_form(outcome="explode")


class TestFormRule(JobTestCase):
	def test_rule_refuses_non_job_form(self):
		with set_user("Administrator"):
			form = frappe.get_doc(
				{"doctype": "Form", "title": "No context", "key": "no-context-form"}
			).insert()
		with self.assertRaisesRegex(frappe.ValidationError, "is not a job form"):
			add_rule("Installation", "_Test Cash", form.name)

	def test_rule_refuses_archived_form(self):
		form = publish_job_form()["form"]
		frappe.db.set_value("Form", form, "status", "Archived")
		with self.assertRaises(frappe.ValidationError):
			add_rule("Installation", "_Test Cash", form)

	def test_rule_refuses_unpublished_active_form(self):
		with set_user("Administrator"):
			form = frappe.get_doc(
				{
					"doctype": "Form",
					"title": "Draft",
					"key": "draft-job-form",
					"context_doctype": "DeployOps Job",
				}
			).insert()
		with self.assertRaises(frappe.ValidationError):
			add_rule("Installation", "_Test Cash", form.name)
		rule = frappe.get_doc(
			{
				"doctype": RULE,
				"job_type": "Installation",
				"equipment_category": "_Test Cash",
				"form": form.name,
				"active": 0,
			}
		).insert(ignore_permissions=True)
		self.assertEqual(rule.form_title, "Draft")

	def test_rule_refuses_duplicate(self):
		form = publish_job_form()["form"]
		add_rule("Installation", "_Test Cash", form)
		with self.assertRaisesRegex(frappe.ValidationError, "This rule already exists"):
			add_rule("Installation", "_Test Cash", form, required=False)
		add_rule("Maintenance", "_Test Cash", form)  # another job type is another rule

	def test_planned_forms_union_required_wins(self):
		second = make_category("_Test Cash Second", [self.cash])
		a, b = publish_job_form()["form"], publish_job_form()["form"]
		add_rule("Installation", "_Test Cash", a, required=False, sort_order=5)
		add_rule("Installation", second, a, required=True, sort_order=2)
		add_rule("Installation", "_Test Cash", b, required=False, sort_order=3)

		self.assertLessEqual({"_Test Cash", second}, rules.categories_for_item(self.cash))
		self.assertEqual(
			rules.planned_forms("Installation", self.cash),
			[
				{"form": a, "required": True, "sort_order": 2},
				{"form": b, "required": False, "sort_order": 3},
			],
		)


class TestPlannedForms(FormJobCase):
	def test_planned_forms_ignores_inactive_disabled_and_other_job_type(self):
		inactive, maintenance, disabled, archived = (publish_job_form()["form"] for _ in range(4))
		frappe.get_doc(
			{
				"doctype": RULE,
				"job_type": "Installation",
				"equipment_category": "_Test Cash",
				"form": inactive,
				"active": 0,
			}
		).insert(ignore_permissions=True)
		add_rule("Maintenance", "_Test Cash", maintenance)
		add_rule("Installation", make_category("_Test Cash Off", [self.cash], enabled=0), disabled)
		add_rule("Installation", "_Test Cash", archived)
		frappe.db.set_value("Form", archived, "status", "Archived")

		expected = [
			{"form": self.form_a["form"], "required": True, "sort_order": 0},
			{"form": self.form_b["form"], "required": False, "sort_order": 1},
		]
		self.assertEqual(rules.planned_forms("Installation", self.cash), expected)
		self.assertEqual(rules.planned_forms("Installation", self.robot), [])
		self.assertEqual(rules.planned_forms("Maintenance", self.cash)[0]["form"], maintenance)

	def test_values_and_catalog(self):
		note = self.delivery_note(
			[{"item_code": self.cash, "serial_and_batch_bundle": fx.make_bundle(self.cash, ["JOB-CR-1"])}]
		)
		job = make_job("Delivery Note", note, assigned_technician=self.technician)
		device = job.devices[0]
		provider = JobFormProvider()
		values = provider.values(job.name, device.name)

		self.assertEqual(values["job"], job.name)
		self.assertEqual(values["job_type"], "Installation")
		self.assertEqual(values["customer_name"], job.customer_name)
		self.assertEqual((values["item_code"], values["serial_no"]), (self.cash, device.serial_no))
		self.assertEqual(values["item_name"], device.item_name)
		self.assertEqual(values["technician"], frappe.db.get_value("User", self.technician, "full_name"))
		self.assertEqual(values["technician_user"], self.technician)
		catalog = {entry["value"]: entry["type"] for entry in provider.value_catalog()}
		self.assertLessEqual(set(values), set(catalog))
		self.assertEqual(catalog["address"], "long_text")
		self.assertEqual(catalog["planned_date"], "date")

		missing = provider.values(job.name, None)
		self.assertEqual(
			(missing["item_code"], missing["item_name"], missing["serial_no"]), (None, None, None)
		)


class TestPlanRows(IntegrationTestCase):
	def test_plan_rows_keeps_override_drops_unplanned_rule(self):
		existing = [
			row("F-OVR", origin="Override", required=0, sort_order=9),
			row("F-OLD"),
			row("F-OTHER", device="D2"),
		]
		planned = [{"form": "F-NEW", "required": True, "sort_order": 1}]
		self.assertEqual(
			rules.plan_rows(existing, planned, "D1"),
			[row("F-NEW", sort_order=1), row("F-OVR", origin="Override", required=0, sort_order=9)],
		)

	def test_plan_rows_keeps_removed_flag_and_submission(self):
		existing = [row("F-A", required=1, sort_order=4, removed=1, submission="SUB-1", flagged=1)]
		planned = [{"form": "F-A", "required": False, "sort_order": 0}]
		self.assertEqual(
			rules.plan_rows(existing, planned, "D1"),
			[row("F-A", required=0, sort_order=0, removed=1, submission="SUB-1", flagged=1)],
		)
