import frappe
from frappe.tests.classes.context_managers import set_user

from deployops.api import forms as forms_api
from deployops.roles import MANAGER, SUPERVISOR
from deployops.tests.forms_utils import RULE, FormJobCase, publish_job_form
from deployops.tests.utils import make_role_user


class TestFormRulesAPI(FormJobCase):
	def test_designer_adds_changes_and_removes_a_rule(self):
		form = publish_job_form()["form"]
		manager = make_role_user(MANAGER)
		with set_user(manager):
			out = forms_api.form_rules(form)
			self.assertIn("Installation", out["job_types"])
			self.assertIn("_Test Cash", out["categories"])
			name = forms_api.save_form_rule(form, "Installation", "_Test Cash", required=1)
			self.assertEqual([r.name for r in forms_api.form_rules(form)["rules"]], [name])
			forms_api.save_form_rule(form, "Installation", "_Test Cash", required=0, active=0, name=name)
			self.assertEqual(frappe.db.get_value(RULE, name, ["required", "active"]), (0, 0))
			with self.assertRaises(frappe.ValidationError):  # same rule twice
				forms_api.save_form_rule(form, "Installation", "_Test Cash")
			forms_api.delete_form_rule(name)
		self.assertFalse(frappe.db.exists(RULE, name))

	def test_rule_must_belong_to_the_form(self):
		other = publish_job_form()["form"]
		rule = frappe.db.get_value(RULE, {"form": self.form_a["form"]})
		with set_user(make_role_user(MANAGER)), self.assertRaises(frappe.PermissionError):
			forms_api.save_form_rule(other, "Installation", "_Test Cash", name=rule)

	def test_supervisor_cannot_manage_rules(self):
		with set_user(make_role_user(SUPERVISOR)):
			for call in (lambda: forms_api.form_rules(self.form_a["form"]),
				lambda: forms_api.save_form_rule(self.form_a["form"], "Installation", "_Test Cash"),
				lambda: forms_api.delete_form_rule(frappe.db.get_value(RULE, {"form": self.form_a["form"]}))):
				with self.assertRaises(frappe.PermissionError):
					call()
