"""Which serials a job's machine may use, per source (#39): a delivery's own serials, an order's
delivered serials before stock, a subscription's allocated machines."""

import frappe
from frappe.tests.classes.context_managers import set_user

from deployops.api import jobs as job_api
from deployops.integrations import delivery_handoff
from deployops.tests import erpnext_fixtures as fx
from deployops.tests.test_job import JOB, JobTestCase, make_job


class OrderSerialsTestCase(JobTestCase):
	def picker(self, job, item=None, delivery_note=None):
		doc = frappe.get_doc(JOB, job)
		filters = {
			"item_code": item or self.cash,
			"company": doc.company,
			"job_type": doc.job_type,
			"source_doctype": doc.source_doctype,
			"source_name": doc.source_name,
			"delivery_note": delivery_note,
		}
		with set_user(self.supervisor):
			return [row[0] for row in job_api.serial_link_query("Serial No", "", "name", 0, 20, filters)]

	def deliver(self, order, serials):
		bundle = fx.make_bundle(self.cash, serials)
		return fx.make_delivery_note(
			self.customer,
			[
				{
					"item_code": self.cash,
					"qty": len(serials),
					"serial_and_batch_bundle": bundle,
					"against_sales_order": order,
				}
			],
		)

	def set_serial(self, job, index, serial):
		with set_user(self.supervisor):
			doc = frappe.get_doc(JOB, job)
			doc.devices[index].serial_no = serial
			doc.save()


class TestSalesOrderSerials(OrderSerialsTestCase):
	def test_a_delivered_order_offers_only_its_delivered_serials(self):
		order = fx.make_sales_order(self.customer, [self.cash]).name
		self.deliver(order, ["JOB-CR-1"])
		job = make_job("Sales Order", order, job_type="Pre-installation").name
		self.assertEqual(frappe.get_doc(JOB, job).devices[0].serial_no, "JOB-CR-1")
		self.assertEqual(self.picker(job), ["JOB-CR-1"])  # not the stock machines JOB-CR-2 / JOB-CR-3
		with self.assertRaisesRegex(frappe.ValidationError, "delivered"):
			self.set_serial(job, 0, "JOB-CR-2")

	def test_undelivered_units_may_use_stock(self):
		order = fx.make_sales_order(self.customer, [self.cash, self.cash]).name
		self.deliver(order, ["JOB-CR-1"])
		job = make_job("Sales Order", order, job_type="Pre-installation").name
		self.assertEqual(self.picker(job), ["JOB-CR-1", "JOB-CR-2", "JOB-CR-3"])
		self.set_serial(job, 1, "JOB-CR-2")  # the undelivered unit: a stock machine is fine
		self.assertEqual([d.serial_no for d in frappe.get_doc(JOB, job).devices], ["JOB-CR-1", "JOB-CR-2"])
		with self.assertRaisesRegex(frappe.ValidationError, "delivered"):
			self.set_serial(job, 0, "JOB-CR-3")  # the delivered unit cannot swap to stock

	def test_an_undelivered_order_still_picks_from_stock(self):
		order = fx.make_sales_order(self.customer, [self.cash]).name
		job = make_job("Sales Order", order, job_type="Pre-installation").name
		self.assertEqual(self.picker(job), ["JOB-CR-1", "JOB-CR-2", "JOB-CR-3"])


class TestDeliveryAndRentalSerials(OrderSerialsTestCase):
	def test_a_machine_from_a_later_delivery_offers_that_deliverys_serials(self):
		order = fx.make_sales_order(self.customer, [self.cash, self.cash]).name
		first = self.deliver(order, ["JOB-CR-1"])
		job = make_job("Delivery Note", first.name, assigned_technician=self.technician).name
		second = self.deliver(order, ["JOB-CR-2"])
		delivery_handoff.on_delivery_note_submit(second)
		self.assertEqual(self.picker(job), ["JOB-CR-1"])
		self.assertEqual(self.picker(job, delivery_note=second.name), ["JOB-CR-2"])

	def test_a_subscription_offers_its_allocated_machines_not_stock(self):
		from deployops.api import allocations as allocation_api

		frappe.get_doc(
			{
				"doctype": "DeployOps Equipment Category",
				"category_name": "_Test Robots",
				"items": [{"item_code": self.robot}],
			}
		).insert(ignore_permissions=True)
		profile = frappe.get_doc("DeployOps Equipment Access Profile", self.supervisor)
		profile.append("categories", {"category": "_Test Robots"})
		profile.save(ignore_permissions=True)
		fx.make_serial("JOB-BB-2", self.robot)
		subscription = fx.make_subscription(self.customer).name
		with set_user(self.supervisor):
			allocation_api.reserve("JOB-BB-1", "Subscription", subscription)
		job = make_job("Subscription", subscription).name
		self.assertEqual(self.picker(job, item=self.robot), ["JOB-BB-1"])  # not the stock JOB-BB-2
