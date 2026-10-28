import frappe
from frappe.tests.classes.context_managers import set_user

from deployops.api import allocations as allocation_api
from deployops.api import jobs as job_api
from deployops.equipment import allocations
from deployops.roles import ADMINISTRATOR, MANAGER, SUPERVISOR
from deployops.tests import erpnext_fixtures as fx
from deployops.tests.test_job import JOB, JobTestCase, make_job
from deployops.tests.utils import make_role_user

ALLOCATION = "DeployOps Equipment Allocation"


class AllocationTestCase(JobTestCase):
	def setUp(self):
		super().setUp()
		frappe.get_doc(
			{
				"doctype": "DeployOps Equipment Category",
				"category_name": "_Test Robots",
				"items": [{"item_code": self.robot}],
			}
		).insert(ignore_permissions=True)
		self.manager = make_role_user(MANAGER)
		self.admin = make_role_user(ADMINISTRATOR)
		for user in (self.supervisor, self.manager, self.technician):
			profile = (
				frappe.get_doc("DeployOps Equipment Access Profile", user)
				if frappe.db.exists("DeployOps Equipment Access Profile", user)
				else frappe.get_doc({"doctype": "DeployOps Equipment Access Profile", "user": user})
			)
			profile.categories = []
			for category in ("_Test Cash", "_Test Robots"):
				profile.append("categories", {"category": category})
			profile.save(ignore_permissions=True)
		fx.make_serial("JOB-BB-2", self.robot)
		self.subscription = fx.make_subscription(self.customer).name

	def reserve_as(self, user, serial_no, source=None, doctype="Subscription"):
		with set_user(user):
			return allocation_api.reserve(serial_no, doctype, source or self.subscription)

	def alloc(self, name):
		return frappe.get_doc(ALLOCATION, name)

	def deploy_rental(self, serial_no="JOB-BB-1"):
		name = self.reserve_as(self.supervisor, serial_no)
		job = make_job("Subscription", self.subscription, assigned_technician=self.technician).name
		frappe.db.set_value(JOB, job, "status", "Pending Review")
		frappe.db.set_value("DeployOps Job Device", {"parent": job}, "device_status", "Completed")
		with set_user(self.supervisor):
			job_api.job_action(job, "approve")
		return name, job


class TestRentalReservation(AllocationTestCase):
	def test_reserve_in_stock_machine(self):
		doc = self.alloc(self.reserve_as(self.supervisor, "JOB-BB-1"))
		self.assertTrue(doc.name.startswith("DO-ALLOC-"))
		self.assertEqual(
			(doc.allocation_type, doc.status, doc.customer), ("Rental", "Reserved", self.customer)
		)
		self.assertEqual((doc.active_serial, doc.item_code), ("JOB-BB-1", self.robot))
		self.assertEqual([e.event for e in doc.events], ["Reserved"])

	def test_reservation_refusals(self):
		fx.make_serial("JOB-SOLD", self.robot, customer="_SomeoneElse")
		self.reserve_as(self.supervisor, "JOB-BB-1")
		other_subscription = fx.make_subscription(self.customer).name
		cases = {
			"not in stock": lambda: self.reserve_as(self.supervisor, "JOB-SOLD"),
			"already allocated": lambda: self.reserve_as(self.supervisor, "JOB-BB-1", other_subscription),
			"cancelled subscription": lambda: self.reserve_as(
				self.supervisor, "JOB-BB-2", fx.make_subscription(self.customer, status="Cancelled").name
			),
		}
		for label, attempt in cases.items():
			with self.subTest(label), self.assertRaises(frappe.ValidationError):
				attempt()

	def test_who_may_reserve(self):
		with self.assertRaises(frappe.PermissionError):
			self.reserve_as(self.technician, "JOB-BB-1")
		profile = frappe.get_doc("DeployOps Equipment Access Profile", self.supervisor)
		profile.categories = profile.categories[:1]  # cash only
		profile.save(ignore_permissions=True)
		with self.assertRaises(frappe.PermissionError):
			self.reserve_as(self.supervisor, "JOB-BB-1")

	def test_database_allows_only_one_active_allocation_per_machine(self):
		first = self.reserve_as(self.supervisor, "JOB-BB-1")
		second = self.reserve_as(self.supervisor, "JOB-BB-2", fx.make_subscription(self.customer).name)
		# Bypass every application check: the database itself refuses a second active allocation.
		with self.assertRaises(Exception) as refused:
			frappe.db.set_value(ALLOCATION, second, "active_serial", "JOB-BB-1")
		self.assertIn("active_serial", str(refused.exception))
		frappe.db.rollback()
		self.assertTrue(first)


class TestRentalLifecycle(AllocationTestCase):
	def test_rental_job_uses_the_reserved_machine_and_approval_deploys_it(self):
		name, job = self.deploy_rental()
		self.assertEqual([d.serial_no for d in frappe.get_doc(JOB, job).devices], ["JOB-BB-1"])
		doc = self.alloc(name)
		self.assertEqual((doc.status, doc.active_serial), ("Deployed", "JOB-BB-1"))
		self.assertTrue(doc.deployed_on)
		self.assertEqual((doc.events[-1].event, doc.events[-1].job), ("Deployed", job))

	def test_return_with_condition_frees_the_machine(self):
		name, _job = self.deploy_rental()
		with set_user(self.technician), self.assertRaises(frappe.PermissionError):
			allocation_api.return_machine(name, "fine")
		with set_user(self.supervisor):
			with self.assertRaises(frappe.ValidationError):
				allocation_api.return_machine(name, "  ")
			self.assertEqual(
				allocation_api.return_machine(name, "Scratch on the tray", "2026-12-01"), "Returned"
			)
		doc = self.alloc(name)
		self.assertEqual(
			(doc.active_serial, str(doc.returned_on), doc.return_condition),
			(None, "2026-12-01", "Scratch on the tray"),
		)
		self.assertTrue(
			self.reserve_as(self.supervisor, "JOB-BB-1", fx.make_subscription(self.customer).name)
		)

	def test_swap_takes_one_back_and_reserves_the_replacement(self):
		name, _job = self.deploy_rental()
		with set_user(self.supervisor):
			new = allocation_api.swap_machine(name, "JOB-BB-2", "Battery no longer charges")
		old, replacement = self.alloc(name), self.alloc(new)
		self.assertEqual((old.status, old.replaced_by, old.active_serial), ("Swapped Out", new, None))
		self.assertEqual(
			(replacement.status, replacement.replaces, replacement.source_name),
			("Reserved", name, self.subscription),
		)
		self.assertEqual(
			[
				d["serial_no"]
				for d in job_api.get_source_details("Subscription", self.subscription)["devices"]
			],
			["JOB-BB-2"],
		)

	def test_only_reservations_are_cancelled_by_manager_or_admin(self):
		name = self.reserve_as(self.supervisor, "JOB-BB-1")
		with set_user(self.supervisor), self.assertRaises(frappe.PermissionError):
			allocation_api.cancel_reservation(name, "x")
		with set_user(self.manager):
			with self.assertRaises(frappe.ValidationError):
				allocation_api.cancel_reservation(name, "")
			self.assertEqual(allocation_api.cancel_reservation(name, "Customer changed plan"), "Cancelled")
		deployed, _job = self.deploy_rental("JOB-BB-2")
		with set_user(self.admin), self.assertRaises(frappe.ValidationError):
			allocation_api.cancel_reservation(deployed, "x")


class TestSaleReservations(AllocationTestCase):
	def order_job(self, items=None):
		order = fx.make_sales_order(self.customer, items or [self.cash]).name
		return order, make_job(
			"Sales Order", order, job_type="Pre-installation", assigned_technician=self.technician
		).name

	def set_serial(self, job, serial_no, user=None):
		with set_user(user or self.technician):
			doc = frappe.get_doc(JOB, job)
			doc.devices[0].serial_no = serial_no
			doc.save()

	def sale(self, serial_no):
		return frappe.db.get_value(
			ALLOCATION,
			{"serial_no": serial_no, "allocation_type": "Sale"},
			["name", "status", "reserved_by_job"],
			as_dict=True,
			order_by="creation desc",
		)

	def test_picking_a_machine_reserves_it_for_the_order(self):
		order, job = self.order_job()
		self.set_serial(job, "JOB-CR-3")
		sale = self.sale("JOB-CR-3")
		self.assertEqual((sale.status, sale.reserved_by_job), ("Reserved", job))
		self.assertEqual(frappe.db.get_value(ALLOCATION, sale.name, "source_name"), order)

	def test_a_reserved_machine_cannot_be_promised_twice(self):
		_order, job = self.order_job()
		self.set_serial(job, "JOB-CR-3")
		_order2, job2 = self.order_job()
		with self.assertRaises(frappe.ValidationError):
			self.set_serial(job2, "JOB-CR-3")
		with self.assertRaises(frappe.ValidationError):
			self.reserve_as(self.supervisor, "JOB-CR-3")  # nor rented out

	def test_changing_or_cancelling_releases_the_reservation(self):
		_order, job = self.order_job()
		self.set_serial(job, "JOB-CR-3")
		first = self.sale("JOB-CR-3").name
		self.set_serial(job, "JOB-CR-2")
		self.assertEqual(frappe.db.get_value(ALLOCATION, first, "status"), "Cancelled")
		self.assertEqual(self.sale("JOB-CR-2").status, "Reserved")

		with set_user(self.manager):
			job_api.job_action(job, "cancel", "Order cancelled")
		self.assertEqual(self.sale("JOB-CR-2").status, "Cancelled")

	def test_delivery_closes_and_cancelled_delivery_reopens(self):
		_order, job = self.order_job()
		self.set_serial(job, "JOB-CR-3")
		note = fx.make_delivery_note(
			self.customer, [{"item_code": self.cash, "serial_no": "JOB-CR-3"}], posting_date="2026-10-20"
		)
		allocations.on_delivery_note_submit(note)
		sale = self.sale("JOB-CR-3")
		self.assertEqual(sale.status, "Delivered")
		doc = self.alloc(sale.name)
		self.assertEqual(
			(doc.active_serial, str(doc.deployed_on), doc.events[-1].reference_name),
			(None, "2026-10-20", note.name),
		)

		allocations.on_delivery_note_cancel(note)
		self.assertEqual(self.sale("JOB-CR-3").status, "Reserved")

	def test_already_delivered_to_this_customer_needs_no_reservation(self):
		fx.make_serial("JOB-MINE", self.cash, customer=self.customer)
		fx.make_serial("JOB-THEIRS", self.cash, customer="_SomeoneElse")
		_order, job = self.order_job()
		self.set_serial(job, "JOB-MINE")
		self.assertIsNone(self.sale("JOB-MINE"))
		with self.assertRaises(frappe.ValidationError):
			self.set_serial(job, "JOB-THEIRS")


class TestAllocationIntegrityAndVisibility(AllocationTestCase):
	def test_status_dates_and_log_cannot_be_edited_directly(self):
		name = self.reserve_as(self.supervisor, "JOB-BB-1")
		for label, edit in {
			"status": lambda d: setattr(d, "status", "Deployed"),
			"active serial": lambda d: setattr(d, "active_serial", None),
			"dates": lambda d: setattr(d, "deployed_on", "2026-01-01"),
			"log": lambda d: d.append("events", {"event": "Deployed"}),
		}.items():
			with self.subTest(label), set_user(self.supervisor):
				doc = self.alloc(name)
				edit(doc)
				with self.assertRaises(frappe.ValidationError):
					doc.save()

	def test_who_sees_which_allocation(self):
		robot = self.reserve_as(self.supervisor, "JOB-BB-1")
		_order, job = TestSaleReservations.order_job(self)
		TestSaleReservations.set_serial(self, job, "JOB-CR-3")
		cash = frappe.db.get_value(ALLOCATION, {"serial_no": "JOB-CR-3"})

		with set_user(self.technician):  # only machines on their assigned jobs
			self.assertEqual(set(frappe.get_list(ALLOCATION, pluck="name")) & {robot, cash}, {cash})
		profile = frappe.get_doc("DeployOps Equipment Access Profile", self.supervisor)
		profile.categories = profile.categories[:1]  # cash only
		profile.save(ignore_permissions=True)
		with set_user(self.supervisor):
			self.assertEqual(set(frappe.get_list(ALLOCATION, pluck="name")) & {robot, cash}, {cash})
			self.assertFalse(frappe.has_permission(ALLOCATION, "read", robot))
		with set_user(self.admin):
			self.assertEqual(set(frappe.get_list(ALLOCATION, pluck="name")) & {robot, cash}, {robot, cash})


class TestSerialHistory(AllocationTestCase):
	def test_history_combines_stock_allocations_and_jobs(self):
		fx.make_bundle(self.robot, ["JOB-BB-1"])
		_name, job = self.deploy_rental()
		with set_user(self.supervisor):
			history = allocation_api.serial_history("JOB-BB-1")
		sources = {row["source"] for row in history}
		self.assertTrue({"ERPNext", "Allocation", "Job"} <= sources)
		self.assertIn("Rental: Deployed", [row["event"] for row in history])
		self.assertIn(job, [row["reference_name"] for row in history])

	def test_a_returned_rental_machine_does_not_block_cancelling_its_job(self):
		allocation, _installation = self.deploy_rental()
		job = make_job(
			"Subscription", self.subscription, job_type="Maintenance", assigned_technician=self.technician
		).name
		with set_user(self.supervisor):
			allocation_api.return_machine(allocation, "Good")  # the machine comes back mid-maintenance
		with set_user(self.manager):
			self.assertEqual(job_api.job_action(job, "cancel", "Rental ended early"), "Cancelled")

	def test_history_shows_only_jobs_and_allocations_the_caller_can_see(self):
		fx.make_bundle(self.robot, ["JOB-BB-1"])
		_name, job = self.deploy_rental()
		other = "_hist-tech@deployops.test"
		frappe.get_doc(
			{
				"doctype": "User",
				"email": other,
				"first_name": "Other",
				"send_welcome_email": 0,
				"roles": [{"role": "DeployOps Technician"}],
			}
		).insert(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "DeployOps Equipment Access Profile",
				"user": other,
				"categories": [{"category": "_Test Robots"}],
			}
		).insert(ignore_permissions=True)
		with set_user(other):
			history = allocation_api.serial_history("JOB-BB-1")
		self.assertEqual({row["source"] for row in history}, {"ERPNext"})  # authorised for the model only
		self.assertNotIn(self.customer, " ".join(str(row["detail"]) for row in history))
		with set_user(self.technician):  # assigned to the job: sees it
			self.assertIn(job, [row["reference_name"] for row in allocation_api.serial_history("JOB-BB-1")])

	def test_history_respects_equipment_access(self):
		profile = frappe.get_doc("DeployOps Equipment Access Profile", self.supervisor)
		profile.categories = profile.categories[:1]
		profile.save(ignore_permissions=True)
		with set_user(self.supervisor), self.assertRaises(frappe.PermissionError):
			allocation_api.serial_history("JOB-BB-1")
