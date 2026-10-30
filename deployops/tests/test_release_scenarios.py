"""Release scenarios (#44 / #30): whole business flows across sources, jobs, allocations, checklists,
signatures, evidence and permissions, each from start to an approved job.

Every scenario walks the same path a real job takes, through the public APIs and the workflow, so a
regression anywhere in the chain shows up here. See docs/RELEASE_TEST_MATRIX.md.
"""

import frappe
from frappe.tests.classes.context_managers import set_user

from deployops.api import allocations as allocation_api
from deployops.api import checklists as checklist_api
from deployops.api import jobs as job_api
from deployops.equipment import allocations
from deployops.integrations import delivery_handoff
from deployops.tests import erpnext_fixtures as fx
from deployops.tests.test_checklists import (
    CASH_INSTALL,
    MAINTENANCE,
    SIGNATURE,
    VALID_SIGNATURE,
    ChecklistTestCase,
)
from deployops.tests.test_job import JOB, make_job

PRE_INSTALL = "DeployOps Cashmatic Pre-installation"
ALLOCATION = "DeployOps Equipment Allocation"


class ReleaseScenarioCase(ChecklistTestCase):
	def act(self, user, job, action, reason=None):
		with set_user(user):
			return job_api.job_action(job, action, reason)

	def machine(self, user, job, index, action, reason=None):
		row = frappe.get_doc(JOB, job).devices[index].name
		with set_user(user):
			return job_api.device_action(job, row, action, reason)

	def checklist(self, job, index=0):
		"""Start, complete and submit the machine's checklist as the technician; return it."""
		row = frappe.get_doc(JOB, job).devices[index].name
		with set_user(self.technician):
			created = checklist_api.start_checklist(job, row)
			doc = self.complete(frappe.get_doc(created["doctype"], created["name"]))
			doc.save()
			doc.submit()
		return doc

	def work_machine(self, job, index=0):
		"""The technician's part for one machine: start it, do its checklist, complete it."""
		self.machine(self.technician, job, index, "start")
		form = self.checklist(job, index)
		self.machine(self.technician, job, index, "complete")
		return form

	def finish(self, job):
		self.act(self.technician, job, "submit")
		return self.act(self.supervisor, job, "approve")

	def deliver(self, order, serials):
		bundle = fx.make_bundle(self.cash, serials)
		note = fx.make_delivery_note(
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
		# What ERPNext's Delivery Note hooks do on submit.
		allocations.on_delivery_note_submit(note)
		delivery_handoff.on_delivery_note_submit(note)
		return note

	def allocation_status(self, serial):
		return frappe.db.get_value(ALLOCATION, {"serial_no": serial}, "status", order_by="creation desc")


class TestSale(ReleaseScenarioCase):
	def test_order_to_preparation_to_delivery_to_approved_installation(self):
		order = fx.make_sales_order(self.customer, [self.cash]).name

		# Preparation: the job starts without a serial; the technician picks the machine.
		prep = make_job(
			"Sales Order", order, job_type="Pre-installation", assigned_technician=self.technician
		).name
		self.assertEqual(self.act(self.supervisor, prep, "start"), "In Preparation")
		with set_user(self.technician):
			doc = frappe.get_doc(JOB, prep)
			doc.devices[0].serial_no = "JOB-CR-1"
			doc.save()
		self.assertEqual(self.allocation_status("JOB-CR-1"), "Reserved")  # promised to this order
		prep_form = self.work_machine(prep)
		self.assertEqual((prep_form.doctype, prep_form.serial_no), (PRE_INSTALL, "JOB-CR-1"))
		self.assertEqual(self.finish(prep), "Completed")

		# Delivery and installation of the same machine.
		note = self.deliver(order, ["JOB-CR-1"])
		self.assertEqual(self.allocation_status("JOB-CR-1"), "Delivered")
		install = make_job("Delivery Note", note.name, assigned_technician=self.technician).name
		self.act(self.supervisor, install, "start")
		self.assertEqual(self.act(self.technician, install, "arrive"), "On Site")
		form = self.work_machine(install)
		self.assertEqual(self.finish(install), "Completed")

		# Traceability: one machine, two locked checklists, each with its snapshot and signatures.
		self.assertEqual((form.doctype, form.serial_no, form.docstatus), (CASH_INSTALL, "JOB-CR-1", 1))
		for done in (prep_form, form):
			self.assertTrue(
				frappe.parse_json(frappe.db.get_value(done.doctype, done.name, "submission_snapshot"))
			)
		self.assertTrue(frappe.get_doc(CASH_INSTALL, form.name).signatures)
		actions = [row.action for row in frappe.get_doc(JOB, install).status_log]
		self.assertEqual(actions[:2], ["start", "arrive"])
		self.assertEqual(actions[-2:], ["submit", "approve"])


class TestRental(ReleaseScenarioCase):
	def test_reserve_install_deploy_then_return(self):
		subscription = fx.make_subscription(self.customer).name
		with set_user(self.supervisor):
			allocation = allocation_api.reserve("JOB-CR-2", "Subscription", subscription)
		job = make_job("Subscription", subscription, assigned_technician=self.technician).name
		self.assertEqual([d.serial_no for d in frappe.get_doc(JOB, job).devices], ["JOB-CR-2"])
		self.act(self.supervisor, job, "start")
		self.act(self.technician, job, "arrive")
		self.work_machine(job)
		self.assertEqual(self.finish(job), "Completed")
		self.assertEqual(frappe.db.get_value(ALLOCATION, allocation, "status"), "Deployed")

		with set_user(self.supervisor):
			allocation_api.return_machine(allocation, "Good")
		self.assertEqual(frappe.db.get_value(ALLOCATION, allocation, "status"), "Returned")
		with set_user(self.supervisor):  # back in the pool: it can be rented again
			self.assertTrue(allocation_api.reserve("JOB-CR-2", "Subscription", subscription))


class TestTwoMachines(ReleaseScenarioCase):
	def test_one_installed_one_blocked_then_cancelled_and_its_serial_freed(self):
		bundle = fx.make_bundle(self.cash, ["JOB-CR-1", "JOB-CR-2"])
		note = fx.make_delivery_note(
			self.customer, [{"item_code": self.cash, "qty": 2, "serial_and_batch_bundle": bundle}]
		).name
		job = make_job("Delivery Note", note, assigned_technician=self.technician).name
		self.act(self.supervisor, job, "start")
		self.act(self.technician, job, "arrive")

		self.work_machine(job, 0)
		self.machine(self.technician, job, 1, "block", "No power socket within 2 m")  # a no-go on site
		with self.assertRaisesRegex(frappe.ValidationError, "is blocked"):  # a blocked machine stops the job
			self.act(self.technician, job, "submit")

		self.machine(self.supervisor, job, 1, "cancel", "Customer will install power next month")
		self.assertEqual(self.finish(job), "Completed")
		self.assertEqual(
			[d.device_status for d in frappe.get_doc(JOB, job).devices], ["Completed", "Cancelled"]
		)

		# The cancelled machine is not stuck: a new job can take it later.
		later = fx.make_delivery_note(
			self.customer,
			[{"item_code": self.cash, "serial_and_batch_bundle": fx.make_bundle(self.cash, ["JOB-CR-2"])}],
		).name
		self.assertEqual(make_job("Delivery Note", later).devices[0].serial_no, "JOB-CR-2")


class TestSerialConflicts(ReleaseScenarioCase):
	def test_one_machine_cannot_be_promised_or_booked_twice(self):
		order = fx.make_sales_order(self.customer, [self.cash]).name
		prep = make_job(
			"Sales Order", order, job_type="Pre-installation", assigned_technician=self.technician
		).name
		with set_user(self.supervisor):
			doc = frappe.get_doc(JOB, prep)
			doc.devices[0].serial_no = "JOB-CR-1"
			doc.save()
		subscription = fx.make_subscription(self.customer).name
		with set_user(self.supervisor), self.assertRaisesRegex(frappe.ValidationError, "already reserved"):
			allocation_api.reserve("JOB-CR-1", "Subscription", subscription)  # already promised to the sale

		other_order = fx.make_sales_order(self.customer, [self.cash]).name
		with self.assertRaisesRegex(
			frappe.ValidationError, "already on open"
		):  # nor a second order's preparation
			make_job(
				"Sales Order",
				other_order,
				job_type="Pre-installation",
				devices=[{"item_code": self.cash, "serial_no": "JOB-CR-1"}],
			)


class TestMaintenance(ReleaseScenarioCase):
	def test_maintenance_visit_to_approved_maintenance_checklist(self):
		visit = fx.make_maintenance_visit(
			self.customer, [{"item_code": self.cash, "serial_no": "JOB-CR-3"}]
		).name
		job = make_job(
			"Maintenance Visit", visit, job_type="Maintenance", assigned_technician=self.technician
		).name
		self.assertEqual(self.act(self.supervisor, job, "start"), "On Site")
		form = self.work_machine(job)
		self.assertEqual(form.doctype, MAINTENANCE)
		self.assertTrue(all(row.completed for row in form.cashbox_tasks))
		self.assertEqual(self.finish(job), "Completed")


class TestPermissionsAcrossTheFlow(ReleaseScenarioCase):
	def test_only_the_people_on_the_job_see_its_records_and_evidence(self):
		job = self.working_job()
		row = frappe.get_doc(JOB, job).devices[0].name
		with set_user(self.technician):
			created = checklist_api.start_checklist(job, row)
		photo = self.attach(created["doctype"], created["name"])[0]
		with set_user(self.technician):
			form = frappe.get_doc(created["doctype"], created["name"])
			form.append("installation_photos", {"image": photo})
			form.keys_receiver_signature = VALID_SIGNATURE
			form.save()

		other = "_release-tech@deployops.test"
		frappe.get_doc(
			{
				"doctype": "User",
				"email": other,
				"first_name": "Other",
				"send_welcome_email": 0,
				"roles": [{"role": "DeployOps Technician"}],
			}
		).insert(ignore_permissions=True)
		file = frappe.get_doc("File", {"file_url": photo})
		cases = (
			(self.technician, True),
			(self.supervisor, True),
			(self.manager, True),
			(other, False),  # a technician not on this job
			("Guest", False),
		)
		for user, allowed in cases:
			with self.subTest(user=user):
				self.assertEqual(bool(frappe.has_permission(JOB, "read", job, user=user)), allowed)
				self.assertEqual(
					bool(frappe.has_permission(CASH_INSTALL, "read", form.name, user=user)), allowed
				)
				self.assertEqual(bool(frappe.has_permission("File", "read", file, user=user)), allowed)
