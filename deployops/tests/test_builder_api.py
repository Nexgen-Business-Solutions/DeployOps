import frappe
from frappe.tests.utils import FrappeTestCase

from deployops.api.forms import form_rule_counts


class TestBuilderAPI(FrappeTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_counts_active_only(self):
		frappe.set_user("Administrator")
		expected = {}
		for row in frappe.get_all("DeployOps Form Rule", filters={"active": 1}, fields=["form"]):
			expected[row.form] = expected.get(row.form, 0) + 1
		self.assertEqual(form_rule_counts(), expected)

	def test_guest_denied(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			form_rule_counts()
