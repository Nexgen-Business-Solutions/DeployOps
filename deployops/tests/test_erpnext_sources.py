import frappe
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user

from deployops.api import sources as api
from deployops.integrations.erpnext_sources import (
	get_source_snapshot,
	validate_serial,
	validate_source,
)
from deployops.roles import ADMINISTRATOR, SUPERVISOR, TECHNICIAN
from deployops.tests import erpnext_fixtures as fx
from deployops.tests.utils import make_role_user


class SourceTestCase(IntegrationTestCase):
	def setUp(self):
		# Every test starts clean.
		self.addCleanup(frappe.db.rollback)
		self.cash = fx.make_item("_Test CR-460")
		self.robot = fx.make_item("_Test BB-PRO")
		self.contact = fx.make_contact("_TestContact")
		self.address = fx.make_address("_TestAddress")
		self.customer = fx.make_customer("_TestCust", contact=self.contact, address=self.address)


class TestValidateSource(SourceTestCase):
	def assert_refused(self, doctype, name, company=None):
		with self.assertRaises(frappe.ValidationError):
			validate_source(doctype, name, company)

	def test_sales_order_states(self):
		self.assertTrue(validate_source("Sales Order", fx.make_sales_order(self.customer, [self.cash]).name))
		self.assert_refused("Sales Order", fx.make_sales_order(self.customer, [self.cash], docstatus=0).name)
		self.assert_refused("Sales Order", fx.make_sales_order(self.customer, [self.cash], docstatus=2).name)
		for status in ("Closed", "On Hold"):
			with self.subTest(status=status):
				self.assert_refused(
					"Sales Order", fx.make_sales_order(self.customer, [self.cash], status=status).name
				)

	def test_delivery_note_states(self):
		row = [{"item_code": self.cash}]
		self.assertTrue(validate_source("Delivery Note", fx.make_delivery_note(self.customer, row).name))
		self.assert_refused("Delivery Note", fx.make_delivery_note(self.customer, row, docstatus=0).name)
		self.assert_refused("Delivery Note", fx.make_delivery_note(self.customer, row, docstatus=2).name)
		self.assert_refused("Delivery Note", fx.make_delivery_note(self.customer, row, is_return=1).name)

	def test_subscription_states(self):
		self.assertTrue(validate_source("Subscription", fx.make_subscription(self.customer).name))
		for status in ("Cancelled", "Completed"):
			with self.subTest(status=status):
				self.assert_refused("Subscription", fx.make_subscription(self.customer, status=status).name)
		self.assert_refused("Subscription", fx.make_subscription("_TestSupplier", party_type="Supplier").name)

	def test_maintenance_visit_states(self):
		purposes = [{"item_code": self.cash}]
		self.assertTrue(
			validate_source("Maintenance Visit", fx.make_maintenance_visit(self.customer, purposes).name)
		)
		self.assertTrue(
			validate_source("Maintenance Visit", fx.make_maintenance_visit(self.customer, purposes, 1).name)
		)
		self.assert_refused("Maintenance Visit", fx.make_maintenance_visit(self.customer, purposes, 2).name)

	def test_maintenance_schedule_states(self):
		rows = [{"item_code": self.cash}]
		self.assertTrue(
			validate_source("Maintenance Schedule", fx.make_maintenance_schedule(self.customer, rows).name)
		)
		self.assert_refused("Maintenance Schedule", fx.make_maintenance_schedule(self.customer, rows, 0).name)
		self.assert_refused("Maintenance Schedule", fx.make_maintenance_schedule(self.customer, rows, 2).name)

	def test_company_boundary(self):
		order = fx.make_sales_order(self.customer, [self.cash]).name
		self.assertTrue(validate_source("Sales Order", order, fx.COMPANY))
		self.assert_refused("Sales Order", order, fx.OTHER_COMPANY)

	def test_unknown_doctype_and_missing_record(self):
		self.assert_refused("Customer", self.customer)
		with self.assertRaises(frappe.DoesNotExistError):
			validate_source("Sales Order", "does-not-exist")


class TestSnapshot(SourceTestCase):
	def test_sales_order_snapshot(self):
		order = fx.make_sales_order(
			self.customer, [self.cash, self.robot], contact_person=self.contact, customer_address=self.address
		)
		snap = get_source_snapshot(order)
		self.assertEqual(snap["customer"], self.customer)
		self.assertEqual(snap["customer_name"], "_TestCust Ltd")
		self.assertEqual(snap["company"], fx.COMPANY)
		self.assertEqual(snap["contact"]["email_id"], "_testcontact@example.com")
		self.assertEqual(snap["address"]["name"], self.address)
		self.assertIn("Douala", snap["address"]["display"])
		self.assertEqual([line["item_code"] for line in snap["lines"]], [self.cash, self.robot])

	def test_contact_and_address_fall_back_to_customer_primary(self):
		snap = get_source_snapshot(fx.make_sales_order(self.customer, [self.cash]))
		self.assertEqual(snap["contact"]["name"], self.contact)
		self.assertEqual(snap["address"]["name"], self.address)

	def test_delivery_note_serials_from_bundle(self):
		bundle = fx.make_bundle(self.cash, ["SN-1", "SN-2"])
		note = fx.make_delivery_note(
			self.customer, [{"item_code": self.cash, "serial_and_batch_bundle": bundle, "serial_no": "OLD-1"}]
		)
		self.assertEqual(get_source_snapshot(note)["lines"][0]["serial_nos"], ["SN-1", "SN-2"])

	def test_delivery_note_serials_from_text_field(self):
		note = fx.make_delivery_note(self.customer, [{"item_code": self.cash, "serial_no": "SN-3\nSN-4"}])
		self.assertEqual(get_source_snapshot(note)["lines"][0]["serial_nos"], ["SN-3", "SN-4"])

	def test_cancelled_bundle_falls_back_to_text_field(self):
		bundle = fx.make_bundle(self.cash, ["SN-X"], cancelled=True)
		note = fx.make_delivery_note(
			self.customer, [{"item_code": self.cash, "serial_and_batch_bundle": bundle, "serial_no": "SN-5"}]
		)
		self.assertEqual(get_source_snapshot(note)["lines"][0]["serial_nos"], ["SN-5"])

	def test_multiple_devices_on_one_delivery_note(self):
		note = fx.make_delivery_note(
			self.customer,
			[{"item_code": self.cash, "serial_no": "SN-6"}, {"item_code": self.robot, "serial_no": "SN-7"}],
		)
		lines = get_source_snapshot(note)["lines"]
		self.assertEqual(
			[(line["item_code"], line["serial_nos"]) for line in lines],
			[(self.cash, ["SN-6"]), (self.robot, ["SN-7"])],
		)

	def test_subscription_never_infers_a_device(self):
		snap = get_source_snapshot(fx.make_subscription(self.customer))
		self.assertEqual(snap["lines"], [])
		self.assertEqual(snap["plans"], ["_Test Rental Plan"])

	def test_maintenance_visit_lines(self):
		visit = fx.make_maintenance_visit(self.customer, [{"item_code": self.cash, "serial_no": "SN-8"}])
		self.assertEqual(get_source_snapshot(visit)["lines"][0]["serial_nos"], ["SN-8"])


class TestValidateSerial(SourceTestCase):
	def test_serial_checks(self):
		fx.make_serial("SN-OK", self.cash)
		self.assertEqual(validate_serial("SN-OK", self.cash, fx.COMPANY).item_code, self.cash)
		with self.assertRaises(frappe.ValidationError):
			validate_serial("SN-OK", self.robot)
		with self.assertRaises(frappe.ValidationError):
			validate_serial("SN-OK", self.cash, fx.OTHER_COMPANY)
		with self.assertRaises(frappe.DoesNotExistError):
			validate_serial("SN-MISSING")


class TestSourceApi(SourceTestCase):
	def setUp(self):
		super().setUp()
		frappe.get_doc(
			{
				"doctype": "DeployOps Equipment Category",
				"category_name": "_Test Cash",
				"items": [{"item_code": self.cash}],
			}
		).insert(ignore_permissions=True)
		self.technician = make_role_user(TECHNICIAN)
		frappe.get_doc(
			{
				"doctype": "DeployOps Equipment Access Profile",
				"user": self.technician,
				"categories": [{"category": "_Test Cash"}],
			}
		).insert(ignore_permissions=True)

	def test_requires_a_deployops_role(self):
		outsider = "_test-outsider@deployops.test"
		frappe.get_doc(
			{"doctype": "User", "email": outsider, "first_name": "Out", "send_welcome_email": 0}
		).insert(ignore_permissions=True)
		order = fx.make_sales_order(self.customer, [self.cash]).name
		with set_user(outsider), self.assertRaises(frappe.PermissionError):
			api.get_source_summary("Sales Order", order)

	def test_lines_are_filtered_to_the_users_equipment(self):
		order = fx.make_sales_order(self.customer, [self.cash, self.robot]).name
		with set_user(self.technician):
			lines = api.get_source_summary("Sales Order", order)["lines"]
		self.assertEqual([line["item_code"] for line in lines], [self.cash])

	def test_source_without_users_equipment_is_refused(self):
		order = fx.make_sales_order(self.customer, [self.robot]).name
		with set_user(self.technician), self.assertRaises(frappe.PermissionError):
			api.get_source_summary("Sales Order", order)

	def test_profiles_also_restrict_supervisor(self):
		order = fx.make_sales_order(self.customer, [self.cash]).name
		with set_user(make_role_user(SUPERVISOR)), self.assertRaises(frappe.PermissionError):
			api.get_source_summary("Sales Order", order)

	def test_admin_sees_every_line(self):
		order = fx.make_sales_order(self.customer, [self.cash, self.robot]).name
		with set_user(make_role_user(ADMINISTRATOR)):
			self.assertEqual(len(api.get_source_summary("Sales Order", order)["lines"]), 2)

	def test_subscription_allowed_without_equipment(self):
		subscription = fx.make_subscription(self.customer).name
		with set_user(self.technician):
			self.assertEqual(
				api.get_source_summary("Subscription", subscription)["plans"], ["_Test Rental Plan"]
			)

	def test_search_returns_only_usable_and_authorised_sources(self):
		usable = fx.make_sales_order(self.customer, [self.cash]).name
		fx.make_sales_order(self.customer, [self.cash], docstatus=0)
		fx.make_sales_order(self.customer, [self.cash], status="Closed")
		fx.make_sales_order(self.customer, [self.robot])
		frappe.clear_messages()
		with set_user(self.technician):
			found = [
				row["name"] for row in api.search_sources("Sales Order", "_TestCust", company=fx.COMPANY)
			]
		self.assertEqual(found, [usable])
		self.assertFalse(frappe.local.message_log)

	def test_company_user_permissions_limit_sources(self):
		from frappe.permissions import add_user_permission

		fx.make_company(fx.OTHER_COMPANY)
		home = fx.make_sales_order(self.customer, [self.cash]).name
		other = fx.make_sales_order(self.customer, [self.cash], company=fx.OTHER_COMPANY).name

		with set_user(self.technician):  # no company restriction: both companies
			self.assertTrue(
				{home, other} <= {r["name"] for r in api.search_sources("Sales Order", "_TestCust")}
			)

		add_user_permission("Company", fx.OTHER_COMPANY, self.technician, applicable_for="Sales Invoice")
		with set_user(self.technician):  # restriction for another DocType only: still both
			self.assertTrue(
				{home, other} <= {r["name"] for r in api.search_sources("Sales Order", "_TestCust")}
			)

		add_user_permission("Company", fx.OTHER_COMPANY, self.technician)
		with set_user(self.technician):
			found = {r["name"] for r in api.search_sources("Sales Order", "_TestCust")}
			self.assertIn(other, found)
			self.assertNotIn(home, found)
			self.assertEqual(api.get_source_summary("Sales Order", other)["name"], other)
			with self.assertRaises(frappe.PermissionError):
				api.get_source_summary("Sales Order", home)

	def test_get_serial_respects_company_user_permissions(self):
		"""#13 review: the caller's companies decide, not the company argument (or its absence)."""
		from frappe.permissions import add_user_permission

		fx.make_company()
		fx.make_company(fx.OTHER_COMPANY)
		fx.make_serial("SN-HOME", self.cash)
		fx.make_serial("SN-AWAY", self.cash, company=fx.OTHER_COMPANY)

		with set_user(self.technician):  # no company restriction: both companies
			self.assertEqual(api.get_serial("SN-HOME")["company"], fx.COMPANY)
			self.assertEqual(api.get_serial("SN-AWAY")["company"], fx.OTHER_COMPANY)

		add_user_permission("Company", fx.COMPANY, self.technician, applicable_for="Sales Invoice")
		with set_user(self.technician):  # restriction for another DocType only: still both
			self.assertEqual(api.get_serial("SN-AWAY")["company"], fx.OTHER_COMPANY)

		add_user_permission("Company", fx.COMPANY, self.technician)
		with set_user(self.technician):
			self.assertEqual(api.get_serial("SN-HOME")["name"], "SN-HOME")
			self.assertEqual(api.get_serial("SN-HOME", self.cash, fx.COMPANY)["name"], "SN-HOME")
			for company in (None, fx.OTHER_COMPANY, fx.COMPANY):
				with self.subTest(company=company), self.assertRaises(frappe.PermissionError):
					api.get_serial("SN-AWAY", company=company)

	def test_serial_pickers_and_history_respect_company_user_permissions(self):
		"""#13 review: the Desk serial pickers and the serial history list only the caller's companies."""
		from frappe.permissions import add_user_permission

		from deployops.api import allocations as allocations_api
		from deployops.api import jobs as jobs_api

		fx.make_company()
		fx.make_company(fx.OTHER_COMPANY)
		fx.make_serial("SN-HOME", self.cash)
		fx.make_serial("SN-AWAY", self.cash, company=fx.OTHER_COMPANY)

		def picked(company=None):
			filters = {"item_code": self.cash, **({"company": company} if company else {})}
			job_picker = jobs_api.serial_link_query("Serial No", "SN-", "name", 0, 20, filters)
			allocation_picker = allocations_api.in_stock_serial_query(
				"Serial No", "SN-", "name", 0, 20, filters
			)
			return {row[0] for row in job_picker}, {row[0] for row in allocation_picker}

		with set_user(self.technician):  # no company restriction: both companies
			self.assertEqual(picked(), ({"SN-HOME", "SN-AWAY"}, {"SN-HOME", "SN-AWAY"}))

		add_user_permission("Company", fx.COMPANY, self.technician)
		with set_user(self.technician):
			self.assertEqual(picked(), ({"SN-HOME"}, {"SN-HOME"}))
			self.assertEqual(picked(fx.OTHER_COMPANY), (set(), set()))  # asking for it doesn't help
			self.assertIsInstance(allocations_api.serial_history("SN-HOME"), list)
			with self.assertRaises(frappe.PermissionError):
				allocations_api.serial_history("SN-AWAY")

	def test_foreign_source_is_refused_before_anything_about_it_is_shown(self):
		"""#13 review: a restricted user learns neither the state nor the company of another company's
		document."""
		from frappe.permissions import add_user_permission

		fx.make_company()
		fx.make_company(fx.OTHER_COMPANY)
		draft = fx.make_sales_order(self.customer, [self.cash], docstatus=0, company=fx.OTHER_COMPANY).name
		add_user_permission("Company", fx.COMPANY, self.technician)
		with set_user(self.technician):
			with self.assertRaises(frappe.PermissionError) as refused:
				api.get_source_summary("Sales Order", draft)
		self.assertNotIn(fx.OTHER_COMPANY, str(refused.exception))

	def test_get_serial_respects_equipment(self):
		fx.make_serial("SN-CASH", self.cash)
		fx.make_serial("SN-ROBOT", self.robot)
		with set_user(self.technician):
			self.assertEqual(api.get_serial("SN-CASH")["item_code"], self.cash)
			with self.assertRaises(frappe.PermissionError):
				api.get_serial("SN-ROBOT")
