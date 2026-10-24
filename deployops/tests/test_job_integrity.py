"""Job integrity (#18 / #19 / #39): audit history, creation, fixed source data, machine rows."""

import frappe
from frappe.tests.classes.context_managers import set_user

from deployops.api import jobs as job_api
from deployops.roles import MANAGER
from deployops.tests import erpnext_fixtures as fx
from deployops.tests.test_job import JOB, JobTestCase, make_job
from deployops.tests.utils import make_role_user


class IntegrityTestCase(JobTestCase):
	def setUp(self):
		super().setUp()
		self.manager = make_role_user(MANAGER)
		frappe.get_doc(
			{
				"doctype": "DeployOps Equipment Access Profile",
				"user": self.manager,
				"categories": [{"category": "_Test Cash"}],
			}
		).insert(ignore_permissions=True)

	def note(self, serial):
		bundle = fx.make_bundle(self.cash, [serial])
		return fx.make_delivery_note(
			self.customer, [{"item_code": self.cash, "serial_and_batch_bundle": bundle}]
		).name

	def started_job(self, serial="JOB-CR-1"):
		job = make_job("Delivery Note", self.note(serial), assigned_technician=self.technician).name
		with set_user(self.supervisor):
			job_api.job_action(job, "start")
		with set_user(self.technician):
			job_api.job_action(job, "arrive")
		return job

	def save_as(self, user, job, change):
		with set_user(user):
			doc = frappe.get_doc(JOB, job)
			change(doc)
			doc.save()


class TestAuditHistory(IntegrityTestCase):
	def test_existing_log_entries_cannot_be_changed(self):
		job = self.started_job()
		changes = {
			"reason": lambda d: setattr(d.status_log[0], "reason", "rewritten"),
			"actor": lambda d: setattr(d.status_log[0], "user", self.manager),
			"action": lambda d: setattr(d.status_log[1], "action", "approve"),
			"removed": lambda d: d.set("status_log", d.status_log[1:]),
		}
		for user in (self.technician, self.supervisor):
			for case, change in changes.items():
				with self.subTest(user=user, case=case), self.assertRaises(frappe.ValidationError):
					self.save_as(user, job, change)

	def test_a_new_job_starts_clean(self):
		with set_user(self.supervisor):
			job = make_job(
				"Delivery Note",
				self.note("JOB-CR-1"),
				devices=[{"item_code": self.cash, "serial_no": "JOB-CR-1", "device_status": "Completed"}],
				status_log=[{"action": "approve", "user": self.manager, "reason": "fabricated"}],
				status="Completed",
			)
		self.assertEqual((job.status, len(job.status_log)), ("Draft", 0))
		self.assertEqual([d.device_status for d in job.devices], ["Pending"])


class TestFixedSourceData(IntegrityTestCase):
	def test_source_snapshot_cannot_be_changed(self):
		job = self.started_job()
		for field in ("customer_name", "address_display", "contact_display"):
			with self.subTest(field=field), self.assertRaises(frappe.ValidationError):
				self.save_as(self.technician, job, lambda d, f=field: d.set(f, "changed"))
		fx.make_company(fx.OTHER_COMPANY)
		for field, value in (("company", fx.OTHER_COMPANY), ("source_name", self.note("JOB-CR-2"))):
			with self.subTest(field=field), self.assertRaises(frappe.ValidationError):
				self.save_as(self.supervisor, job, lambda d, f=field, v=value: d.set(f, v))

	def test_job_type_is_fixed_once_work_has_started(self):
		order = fx.make_sales_order(self.customer, [self.cash]).name
		job = make_job(
			"Sales Order", order, job_type="Pre-installation", assigned_technician=self.technician
		).name
		with set_user(self.supervisor):
			job_api.job_action(job, "start")
		with self.assertRaises(frappe.ValidationError):
			self.save_as(self.supervisor, job, lambda d: d.set("job_type", "Maintenance"))


class TestMachineRows(IntegrityTestCase):
	def test_no_more_machines_than_the_order_covers(self):
		order = fx.make_sales_order(self.customer, [self.cash]).name
		job = make_job("Sales Order", order, job_type="Pre-installation").name
		with self.assertRaises(frappe.ValidationError):
			self.save_as(self.supervisor, job, lambda d: d.append("devices", {"item_code": self.cash}))

	def test_a_cancelled_machine_frees_its_serial(self):
		job = self.started_job("JOB-CR-1")
		row = frappe.get_doc(JOB, job).devices[0].name
		with set_user(self.supervisor):
			job_api.device_action(job, row, "cancel", "Wrong machine delivered")
			replacement = make_job("Delivery Note", self.note("JOB-CR-1"))
		self.assertEqual(replacement.devices[0].serial_no, "JOB-CR-1")

	def test_manager_can_cancel_after_the_technicians_access_is_revoked(self):
		job = self.started_job()
		profile = frappe.get_doc("DeployOps Equipment Access Profile", self.technician)
		profile.categories = []
		profile.save(ignore_permissions=True)
		with set_user(self.manager):
			self.assertEqual(job_api.job_action(job, "cancel", "Customer withdrew"), "Cancelled")
