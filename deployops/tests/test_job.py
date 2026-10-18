import frappe
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user

from deployops.api import jobs as job_api
from deployops.roles import MANAGER, SUPERVISOR, TECHNICIAN
from deployops.tests import erpnext_fixtures as fx
from deployops.tests.utils import make_role_user

JOB = "DeployOps Job"


def make_job(source_doctype, source_name, job_type="Installation", devices=None, **fields):
	doc = {"doctype": JOB, "job_type": job_type, "source_doctype": source_doctype, "source_name": source_name}
	doc["company"] = fields.pop("company", fx.COMPANY)
	if devices is not None:
		doc["devices"] = devices
	doc.update(fields)
	return frappe.get_doc(doc).insert()


class JobTestCase(IntegrationTestCase):
	def setUp(self):
		self.addCleanup(frappe.db.rollback)
		fx.make_company()
		fx.make_company(fx.OTHER_COMPANY)
		self.cash = fx.make_item("_Test CR-460")
		self.robot = fx.make_item("_Test BB-PRO")
		self.spare = fx.make_item("_Test Roll", serialized=False)
		self.customer = fx.make_customer(
			"_TestJobCust",
			contact=fx.make_contact("_TestJobContact"),
			address=fx.make_address("_TestJobAddr"),
		)
		for serial, item in (
			("JOB-CR-1", self.cash),
			("JOB-CR-2", self.cash),
			("JOB-CR-3", self.cash),
			("JOB-BB-1", self.robot),
		):
			fx.make_serial(serial, item)

		frappe.get_doc(
			{
				"doctype": "DeployOps Equipment Category",
				"category_name": "_Test Cash",
				"items": [{"item_code": self.cash}],
			}
		).insert(ignore_permissions=True)
		self.technician = make_role_user(TECHNICIAN)
		self.supervisor = make_role_user(SUPERVISOR)
		for user in (self.technician, self.supervisor):
			frappe.get_doc(
				{
					"doctype": "DeployOps Equipment Access Profile",
					"user": user,
					"categories": [{"category": "_Test Cash"}],
				}
			).insert(ignore_permissions=True)

	def delivery_note(self, rows=None):
		rows = rows or [
			{
				"item_code": self.cash,
				"serial_and_batch_bundle": fx.make_bundle(self.cash, ["JOB-CR-1", "JOB-CR-2"]),
			},
			{"item_code": self.robot, "serial_no": "JOB-BB-1"},
		]
		return fx.make_delivery_note(self.customer, rows).name


class TestJobCreation(JobTestCase):
	def test_from_sales_order_snapshot_and_devices(self):
		order = fx.make_sales_order(self.customer, [self.cash, self.robot, self.spare])
		order.items[0].db_set("qty", 2)
		job = make_job("Sales Order", order.name, job_type="Pre-installation")

		self.assertTrue(job.name.startswith("DO-JOB-"))
		self.assertEqual(job.status, "Draft")
		self.assertEqual((job.customer, job.customer_name), (self.customer, "_TestJobCust Ltd"))
		self.assertEqual(job.contact, "_TestJobContact")
		self.assertIn("_testjobcontact@example.com", job.contact_display)
		self.assertEqual(job.address, "_TestJobAddr")
		self.assertIn("Douala", job.address_display)
		# 2 cash units + 1 robot; the non-serial roll is not equipment
		self.assertEqual([d.item_code for d in job.devices], [self.cash, self.cash, self.robot])
		self.assertTrue(all(not d.serial_no and d.device_status == "Pending" for d in job.devices))

	def test_from_delivery_note_one_row_per_serial(self):
		job = make_job("Delivery Note", self.delivery_note())
		self.assertEqual(
			[(d.item_code, d.serial_no) for d in job.devices],
			[(self.cash, "JOB-CR-1"), (self.cash, "JOB-CR-2"), (self.robot, "JOB-BB-1")],
		)

	def test_from_subscription_devices_are_added_explicitly(self):
		subscription = fx.make_subscription(self.customer).name
		job = make_job(
			"Subscription", subscription, devices=[{"item_code": self.robot, "serial_no": "JOB-BB-1"}]
		)
		self.assertEqual(job.devices[0].serial_no, "JOB-BB-1")
		self.assertEqual(make_job("Subscription", subscription, job_type="Pre-installation").devices, [])

	def test_unusable_source_and_wrong_company_refused(self):
		draft = fx.make_sales_order(self.customer, [self.cash], docstatus=0).name
		with self.assertRaises(frappe.ValidationError):
			make_job("Sales Order", draft, job_type="Pre-installation")
		order = fx.make_sales_order(self.customer, [self.cash]).name
		with self.assertRaises(frappe.ValidationError):
			make_job("Sales Order", order, job_type="Pre-installation", company=fx.OTHER_COMPANY)

	def test_make_job_api(self):
		order = fx.make_sales_order(self.customer, [self.cash]).name
		name = job_api.make_job("Sales Order", order, "Pre-installation")
		self.assertEqual(frappe.db.get_value(JOB, name, "source_name"), order)


class TestJobDeviceRules(JobTestCase):
	def assert_refused(self, *args, **kwargs):
		with self.assertRaises(frappe.ValidationError):
			make_job(*args, **kwargs)

	def test_device_rules(self):
		note = self.delivery_note()
		order = fx.make_sales_order(self.customer, [self.cash]).name
		cases = {
			"item not on source": ("Sales Order", order, "Pre-installation", [{"item_code": self.robot}]),
			"non-serial item": ("Sales Order", order, "Pre-installation", [{"item_code": self.spare}]),
			"serial not on the delivery": (
				"Delivery Note",
				note,
				"Installation",
				[{"item_code": self.cash, "serial_no": "JOB-CR-3"}],
			),
			"serial of another item": (
				"Delivery Note",
				note,
				"Installation",
				[{"item_code": self.cash, "serial_no": "JOB-BB-1"}],
			),
			"duplicate serial": (
				"Delivery Note",
				note,
				"Installation",
				[
					{"item_code": self.cash, "serial_no": "JOB-CR-1"},
					{"item_code": self.cash, "serial_no": "JOB-CR-1"},
				],
			),
		}
		for label, (doctype, name, job_type, devices) in cases.items():
			with self.subTest(label):
				self.assert_refused(doctype, name, job_type=job_type, devices=devices)

	def test_serial_required_for_installation_and_maintenance(self):
		order = fx.make_sales_order(self.customer, [self.cash]).name
		self.assertEqual(len(make_job("Sales Order", order, job_type="Pre-installation").devices), 1)
		for job_type in ("Installation", "Maintenance"):
			with self.subTest(job_type):
				self.assert_refused("Sales Order", order, job_type=job_type)

	def test_no_double_booking_of_open_jobs(self):
		note = self.delivery_note()
		devices = [{"item_code": self.cash, "serial_no": "JOB-CR-1"}]
		first = make_job("Delivery Note", note, devices=devices)
		self.assert_refused("Delivery Note", note, devices=devices)

		# a different job type may use the same serial
		visit = fx.make_maintenance_visit(
			self.customer, [{"item_code": self.cash, "serial_no": "JOB-CR-1"}]
		).name
		make_job("Maintenance Visit", visit, job_type="Maintenance")

		first.db_set("status", "Completed")
		make_job("Delivery Note", note, devices=devices)

	def test_status_changes_only_through_workflow(self):
		job = make_job("Delivery Note", self.delivery_note())
		job.status = "Completed"
		with self.assertRaises(frappe.ValidationError):
			job.save()

	def test_equipment_category_must_cover_devices(self):
		with self.assertRaises(frappe.ValidationError):
			make_job("Delivery Note", self.delivery_note(), equipment_category="_Test Cash")
		job = make_job(
			"Delivery Note",
			self.delivery_note([{"item_code": self.cash, "serial_no": "JOB-CR-3"}]),
			equipment_category="_Test Cash",
		)
		self.assertEqual(job.equipment_category, "_Test Cash")


class TestJobAssignment(JobTestCase):
	def test_assignee_must_be_technician_with_equipment_access(self):
		note = self.delivery_note([{"item_code": self.cash, "serial_no": "JOB-CR-3"}])
		self.assertEqual(
			make_job("Delivery Note", note, assigned_technician=self.technician).assigned_technician,
			self.technician,
		)

		with self.assertRaises(frappe.ValidationError):
			make_job(
				"Delivery Note", self.delivery_note(), assigned_technician=self.technician
			)  # robot not allowed
		with self.assertRaises(frappe.ValidationError):
			make_job(
				"Sales Order",
				fx.make_sales_order(self.customer, [self.cash]).name,
				job_type="Pre-installation",
				assigned_technician=self.supervisor,
			)  # not a Technician


class TestJobPermissions(JobTestCase):
	def test_supervisor_creates_with_only_their_equipment(self):
		order = fx.make_sales_order(self.customer, [self.cash, self.robot]).name
		with set_user(self.supervisor):
			job = make_job("Sales Order", order, job_type="Pre-installation")
			self.assertEqual([d.item_code for d in job.devices], [self.cash])

			with self.assertRaises(frappe.PermissionError):
				make_job(
					"Sales Order", order, job_type="Pre-installation", devices=[{"item_code": self.robot}]
				)

			robot_only = fx.make_sales_order(self.customer, [self.robot]).name
			with self.assertRaises(frappe.PermissionError):
				make_job("Sales Order", robot_only, job_type="Pre-installation")

	def test_technician_cannot_create(self):
		order = fx.make_sales_order(self.customer, [self.cash]).name
		with set_user(self.technician), self.assertRaises(frappe.PermissionError):
			make_job("Sales Order", order, job_type="Pre-installation")

	def test_technician_sees_only_assigned_jobs(self):
		mine = make_job(
			"Sales Order",
			fx.make_sales_order(self.customer, [self.cash]).name,
			job_type="Pre-installation",
			assigned_technician=self.technician,
		)
		other = make_job(
			"Sales Order", fx.make_sales_order(self.customer, [self.cash]).name, job_type="Pre-installation"
		)

		with set_user(self.technician):
			self.assertEqual(frappe.get_list(JOB, pluck="name"), [mine.name])
			self.assertTrue(frappe.has_permission(JOB, "read", mine.name))
			self.assertFalse(frappe.has_permission(JOB, "read", other.name))
		# Managers see jobs within their equipment profile (#12).
		manager = make_role_user(MANAGER)
		frappe.get_doc(
			{
				"doctype": "DeployOps Equipment Access Profile",
				"user": manager,
				"categories": [{"category": "_Test Cash"}],
			}
		).insert(ignore_permissions=True)
		with set_user(manager):
			self.assertEqual(set(frappe.get_list(JOB, pluck="name")), {mine.name, other.name})

	def test_technician_cannot_reassign_or_change_planning(self):
		job = make_job(
			"Sales Order",
			fx.make_sales_order(self.customer, [self.cash]).name,
			job_type="Pre-installation",
			assigned_technician=self.technician,
			planned_date="2026-11-01",
		)
		with set_user(self.technician):
			doc = frappe.get_doc(JOB, job.name)
			doc.assigned_technician = None
			doc.planned_date = "2026-12-24"
			doc.devices[0].serial_no = "JOB-CR-3"
			doc.save()
		doc.reload()
		# level-1 fields are reset to the saved values; the device row (level 0) is the technician's to fill
		self.assertEqual((doc.assigned_technician, str(doc.planned_date)), (self.technician, "2026-11-01"))
		self.assertEqual(doc.devices[0].serial_no, "JOB-CR-3")


class TestJobPickers(JobTestCase):
	def test_source_picker_lists_usable_sources(self):
		usable = fx.make_sales_order(self.customer, [self.cash]).name
		fx.make_sales_order(self.customer, [self.cash], docstatus=0)
		with set_user(self.supervisor):
			rows = job_api.source_link_query(
				"Sales Order", "_TestJob", "name", 0, 20, {"company": fx.COMPANY}
			)
		self.assertEqual([row[0] for row in rows], [usable])

	def test_serial_picker_offers_the_deliverys_serials(self):
		note = self.delivery_note()
		filters = {
			"item_code": self.cash,
			"company": fx.COMPANY,
			"job_type": "Installation",
			"source_doctype": "Delivery Note",
			"source_name": note,
		}
		with set_user(self.supervisor):
			rows = job_api.serial_link_query("Serial No", "", "name", 0, 20, filters)
			self.assertEqual([row[0] for row in rows], ["JOB-CR-1", "JOB-CR-2"])
			filters["item_code"] = self.robot
			self.assertEqual(job_api.serial_link_query("Serial No", "", "name", 0, 20, filters), [])


class TestTechnicianPicker(JobTestCase):
	def test_lists_website_user_technicians_authorised_for_the_jobs_machines(self):
		self.assertEqual(frappe.db.get_value("User", self.technician, "user_type"), "Website User")
		with set_user(self.supervisor):
			names = [
				row[0]
				for row in job_api.technician_link_query(
					"User", "", "name", 0, 20, {"item_codes": [self.cash]}
				)
			]
			self.assertIn(self.technician, names)
			self.assertNotIn(self.supervisor, names)  # not a Technician

			robot = job_api.technician_link_query(
				"User", "", "name", 0, 20, {"item_codes": [self.cash, self.robot]}
			)
			self.assertNotIn(self.technician, [row[0] for row in robot])  # not authorised for the robot


class TestSourceDetailsOnChange(JobTestCase):
	"""What the form fills in when a source is picked (deployops.api.jobs.get_source_details)."""

	def rows(self, details):
		return [(d["item_code"], d["serial_no"]) for d in details["devices"]]

	def test_delivery_note_fills_machines_with_serials(self):
		details = job_api.get_source_details("Delivery Note", self.delivery_note())
		self.assertEqual(
			self.rows(details), [(self.cash, "JOB-CR-1"), (self.cash, "JOB-CR-2"), (self.robot, "JOB-BB-1")]
		)
		self.assertEqual((details["customer"], details["contact"]), (self.customer, "_TestJobContact"))
		self.assertIn("Douala", details["address_display"])
		self.assertEqual(details["company"], fx.COMPANY)

	def test_delivered_order_takes_serials_from_its_deliveries_minus_returns(self):
		order = fx.make_sales_order(self.customer, [self.cash])
		order.items[0].db_set("qty", 3)
		note = fx.make_delivery_note(
			self.customer,
			[{"item_code": self.cash, "serial_no": "JOB-CR-1\nJOB-CR-2", "against_sales_order": order.name}],
		)
		fx.make_delivery_note(
			self.customer,
			[{"item_code": self.cash, "serial_no": "JOB-CR-2"}],
			is_return=1,
			return_against=note.name,
		)
		details = job_api.get_source_details("Sales Order", order.name)
		self.assertEqual(self.rows(details), [(self.cash, "JOB-CR-1"), (self.cash, None), (self.cash, None)])

	def test_undelivered_order_leaves_serials_to_pick(self):
		order = fx.make_sales_order(self.customer, [self.cash, self.spare])
		self.assertEqual(
			self.rows(job_api.get_source_details("Sales Order", order.name)), [(self.cash, None)]
		)

	def test_form_rows_match_what_saving_creates(self):
		order = fx.make_sales_order(self.customer, [self.cash, self.robot]).name
		with set_user(self.supervisor):
			details = job_api.get_source_details("Sales Order", order)
			job = make_job("Sales Order", order, job_type="Pre-installation")
		self.assertEqual(self.rows(details), [(self.cash, None)])
		self.assertEqual([(d.item_code, d.serial_no) for d in job.devices], self.rows(details))

	def test_source_without_users_equipment_is_refused(self):
		robot_only = fx.make_sales_order(self.customer, [self.robot]).name
		with set_user(self.supervisor), self.assertRaises(frappe.PermissionError):
			job_api.get_source_details("Sales Order", robot_only)
