"""Delivery Note handoff to installation jobs (#16 / #43): per-device rows, partial deliveries,
returns, cancellations and mismatches."""

import frappe.model.document
from unittest.mock import patch

import frappe
from frappe.tests.classes.context_managers import set_user

from deployops.integrations import delivery_handoff, erpnext_sources
from deployops.tests import erpnext_fixtures as fx
from deployops.tests.test_job import JOB, JobTestCase, make_job


class DeliveryTestCase(JobTestCase):
	def note(self, serials, order=None, item=None, **extra):
		item = item or self.cash
		row = {
			"item_code": item,
			"serial_and_batch_bundle": fx.make_bundle(item, serials),
			"qty": len(serials),
		}
		if order:
			row["against_sales_order"] = order
		return fx.make_delivery_note(self.customer, [row], **extra)

	def order(self, items=None):
		return fx.make_sales_order(self.customer, items or [self.cash, self.cash]).name

	def job_for(self, note):
		return make_job("Delivery Note", note.name, assigned_technician=self.technician).name

	def rows(self, job):
		return [(r.serial_no, r.delivery_note, r.source_issue) for r in frappe.get_doc(JOB, job).devices]

	def cancel(self, note):
		"""Cancel a delivery as ERPNext does: the note and its serial bundles."""
		frappe.db.set_value("Delivery Note", note.name, "docstatus", 2)
		for row in note.items:
			if row.serial_and_batch_bundle:
				frappe.db.set_value("Serial and Batch Bundle", row.serial_and_batch_bundle, "is_cancelled", 1)
		note.reload()
		delivery_handoff.on_delivery_note_cancel(note)

	def comments(self, job):
		return frappe.get_all(
			"Comment", filters={"reference_doctype": JOB, "reference_name": job}, pluck="content"
		)


class TestPerDeviceRows(DeliveryTestCase):
	def test_each_delivered_serial_gets_its_own_row(self):
		note = fx.make_delivery_note(
			self.customer,
			[
				{
					"item_code": self.cash,
					"qty": 2,
					"serial_and_batch_bundle": fx.make_bundle(self.cash, ["JOB-CR-1", "JOB-CR-2"]),
				},
				{"item_code": self.robot, "serial_no": "JOB-BB-1"},
			],
		)
		job = make_job("Delivery Note", note.name).name
		self.assertEqual(
			self.rows(job),
			[("JOB-CR-1", note.name, None), ("JOB-CR-2", note.name, None), ("JOB-BB-1", note.name, None)],
		)
		self.assertEqual({r.device_status for r in frappe.get_doc(JOB, job).devices}, {"Pending"})

	def test_a_serial_not_on_the_delivery_is_refused(self):
		note = self.note(["JOB-CR-1"])
		with self.assertRaises(frappe.ValidationError):
			make_job("Delivery Note", note.name, devices=[{"item_code": self.cash, "serial_no": "JOB-CR-3"}])


class TestPartialDeliveries(DeliveryTestCase):
	def test_a_later_delivery_of_the_order_is_added_to_the_open_job(self):
		order = self.order()
		first = self.note(["JOB-CR-1"], order)
		job = self.job_for(first)
		second = self.note(["JOB-CR-2"], order)
		delivery_handoff.on_delivery_note_submit(second)

		self.assertEqual(self.rows(job), [("JOB-CR-1", first.name, None), ("JOB-CR-2", second.name, None)])
		self.assertTrue(any(second.name in c for c in self.comments(job)))
		with self.assertRaises(frappe.ValidationError):  # its machine is already on the open job
			make_job("Delivery Note", second.name)

		delivery_handoff.on_delivery_note_submit(second)  # submitted twice: nothing added twice
		self.assertEqual(len(self.rows(job)), 2)

	def test_other_orders_and_closed_or_reviewed_jobs_are_left_alone(self):
		order = self.order()
		job = self.job_for(self.note(["JOB-CR-1"], order))

		other = self.note(["JOB-CR-2"], self.order())
		delivery_handoff.on_delivery_note_submit(other)
		self.assertEqual(len(self.rows(job)), 1)

		frappe.db.set_value(JOB, job, "status", "Pending Review")
		later = self.note(["JOB-CR-3"], order)
		delivery_handoff.on_delivery_note_submit(later)
		self.assertEqual(len(self.rows(job)), 1)
		self.assertTrue(any("waiting for review" in c for c in self.comments(job)))

		frappe.db.set_value(JOB, job, "status", "Completed")
		delivery_handoff.on_delivery_note_submit(later)
		self.assertEqual(len(self.rows(job)), 1)

	def test_a_machine_the_technician_may_not_handle_is_not_added(self):
		order = self.order([self.cash, self.robot])
		job = self.job_for(self.note(["JOB-CR-1"], order))
		robot = fx.make_delivery_note(
			self.customer, [{"item_code": self.robot, "serial_no": "JOB-BB-1", "against_sales_order": order}]
		)
		delivery_handoff.on_delivery_note_submit(robot)
		self.assertEqual(len(self.rows(job)), 1)
		self.assertTrue(any("skipped" in c for c in self.comments(job)))


class TestReturnsAndCancellations(DeliveryTestCase):
	def setUp(self):
		super().setUp()
		self.delivery = self.note(["JOB-CR-1", "JOB-CR-2"])
		self.job = self.job_for(self.delivery)

	def test_a_return_flags_the_machine_and_its_cancellation_clears_the_flag(self):
		ret = self.note(["JOB-CR-2"], is_return=1, return_against=self.delivery.name)
		delivery_handoff.on_delivery_note_submit(ret)
		self.assertEqual(
			self.rows(self.job),
			[
				("JOB-CR-1", self.delivery.name, None),
				("JOB-CR-2", self.delivery.name, f"Returned on {ret.name}"),
			],
		)
		self.assertEqual(
			[r.device_status for r in frappe.get_doc(JOB, self.job).devices], ["Pending", "Pending"]
		)  # flagged only; a supervisor decides

		delivery_handoff.on_delivery_note_cancel(ret)
		self.assertEqual(self.rows(self.job)[1][2], None)

	def test_a_cancelled_delivery_flags_its_machines(self):
		self.cancel(self.delivery)
		issue = f"Delivery Note {self.delivery.name} was cancelled"
		self.assertEqual([r[2] for r in self.rows(self.job)], [issue, issue])

	def test_a_cancelled_later_delivery_flags_only_its_machine_and_the_job_still_saves(self):
		order = self.order()
		first = self.note(["JOB-CR-3"], order)
		job = self.job_for(first)
		second = self.note(["JOB-CR-1"], order)
		frappe.db.set_value(JOB, self.job, "status", "Cancelled")  # free JOB-CR-1 from the setUp job
		delivery_handoff.on_delivery_note_submit(second)
		self.cancel(second)
		self.assertEqual(
			self.rows(job),
			[
				("JOB-CR-3", first.name, None),
				("JOB-CR-1", second.name, f"Delivery Note {second.name} was cancelled"),
			],
		)
		with set_user(self.supervisor):
			doc = frappe.get_doc(JOB, job)
			doc.planned_date = "2026-11-02"
			doc.save()  # a cancelled delivery on a saved row does not block the job

	def test_a_handoff_error_never_reaches_the_delivery_note(self):
		def broken(doc):
			frappe.throw("job problem")

		messages = len(frappe.local.message_log)
		with patch.object(frappe, "log_error") as log_error:
			delivery_handoff._guarded(self.delivery, broken)  # does not raise
		self.assertEqual(len(frappe.local.message_log), messages)
		log_error.assert_called_once_with(title=f"DeployOps delivery handoff failed for {self.delivery.name}")

	def test_delivery_details_are_system_only(self):
		with set_user(self.technician), self.assertRaises(frappe.ValidationError):
			job = frappe.get_doc(JOB, self.job)
			job.devices[0].source_issue = None if job.devices[0].source_issue else "cleared by hand"
			job.save()
		unrelated = self.note(["JOB-CR-3"])
		with self.assertRaises(frappe.ValidationError):
			job = frappe.get_doc(JOB, self.job)
			job.devices[1].delivery_note = unrelated.name
			job.flags.delivery_handoff = True
			job.save(ignore_permissions=True)


class TestP2aOrderMismatchGuard(DeliveryTestCase):
	"""P2a: open_job_for_order must not return a job whose source DN shares no SO
	with the current DN (defense against two concurrent orders for the same customer)."""

	def test_guard_fires_when_earlier_dn_shares_no_so_with_current_dn(self):
		"""The P2a guard returns None when delivery_orders(source_dn) ∩ current_orders = ∅."""
		so1 = self.order()
		so2 = self.order()

		# dn1 covers BOTH so1 and so2 so it naturally appears in the SQL 'earlier' list
		# when processing any DN against so2.  Job-1 is opened from dn1.
		dn1 = fx.make_delivery_note(
			self.customer,
			[
				{
					"item_code": self.cash,
					"serial_and_batch_bundle": fx.make_bundle(self.cash, ["JOB-CR-1"]),
					"qty": 1,
					"against_sales_order": so1,
				},
				{
					"item_code": self.cash,
					"serial_and_batch_bundle": fx.make_bundle(self.cash, ["JOB-CR-2"]),
					"qty": 1,
					"against_sales_order": so2,
				},
			],
		)
		job1_name = self.job_for(dn1)

		# dn2 covers so2 only.
		dn2 = self.note(["JOB-CR-3"], so2)

		# Sanity: without the mock, dn1 truly covers so2 so the guard correctly lets
		# job1 through (shared SO-2).
		real_result = delivery_handoff.open_job_for_order(dn2)
		self.assertIsNotNone(real_result)
		self.assertEqual(real_result.name, job1_name)

		# Now simulate the guard scenario: dn1 is found in 'earlier' (it has a so2 item)
		# but delivery_orders says dn1 only covers so1 (no overlap with dn2's {so2}).
		# The guard must detect the empty intersection and return None.
		original = erpnext_sources.delivery_orders

		def patched_delivery_orders(dn):
			if dn == dn1.name:
				return {so1}  # dn1 covers only so1 → no overlap with dn2's {so2}
			return original(dn)

		with patch.object(erpnext_sources, "delivery_orders", patched_delivery_orders):
			guarded_result = delivery_handoff.open_job_for_order(dn2)

		self.assertIsNone(guarded_result)

	def test_different_orders_same_customer_do_not_cross_attach(self):
		"""End-to-end: a DN for SO-2 is not added to the job opened for SO-1."""
		so1 = self.order()
		so2 = self.order()

		dn1 = self.note(["JOB-CR-1"], so1)
		job1_name = self.job_for(dn1)

		dn2 = self.note(["JOB-CR-2"], so2)
		delivery_handoff.on_delivery_note_submit(dn2)

		# Job-1 must still hold only dn1's machine.
		self.assertEqual(self.rows(job1_name), [("JOB-CR-1", dn1.name, None)])


class TestP2bPerDeviceSaveResilience(DeliveryTestCase):
	"""P2b: devices are saved one at a time; a failed device is skipped, others are still added."""

	def test_first_device_added_when_second_save_fails(self):
		"""If one device's save raises ValidationError the others are unaffected."""
		so = self.order()
		dn1 = self.note(["JOB-CR-1"], so)
		job_name = self.job_for(dn1)

		# dn2 delivers two more machines against the same order.
		dn2 = self.note(["JOB-CR-2", "JOB-CR-3"], so)

		# Simulate: the second DeployOps Job save (JOB-CR-3) raises ValidationError.
		save_count = [0]
		original_save = frappe.model.document.Document.save

		def patched_save(instance, **kwargs):
			if instance.doctype == "DeployOps Job":
				save_count[0] += 1
				if save_count[0] == 2:
					raise frappe.ValidationError("simulated per-device failure")
			return original_save(instance, **kwargs)

		with patch.object(frappe.model.document.Document, "save", patched_save):
			delivery_handoff.on_delivery_note_submit(dn2)

		rows = self.rows(job_name)
		serial_nos = [r[0] for r in rows]

		# JOB-CR-1 was there before; JOB-CR-2 succeeded; JOB-CR-3 was skipped.
		self.assertIn("JOB-CR-1", serial_nos)
		self.assertIn("JOB-CR-2", serial_nos)
		self.assertNotIn("JOB-CR-3", serial_nos)

		# Summary comment mentions both the added count and the skipped count.
		comments = self.comments(job_name)
		self.assertTrue(any("1 machine(s) added" in c for c in comments))
		self.assertTrue(any("1 skipped" in c for c in comments))

		# The job must not be left in a broken state.
		doc = frappe.get_doc(JOB, job_name)
		doc.save()  # must not raise
