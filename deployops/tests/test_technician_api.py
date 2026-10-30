"""The React technician app's API (deployops.api.technician)."""

import frappe
from frappe.tests.classes.context_managers import set_user

from deployops.api import technician as api
from deployops.roles import TECHNICIAN
from deployops.tests.test_checklists import (
	CASH_INSTALL,
	ChecklistTestCase,
	MAINTENANCE,
	SIGNATURE,
	VALID_SIGNATURE,
)

CARD = "cashmatic-onsite"


class TechnicianApiTestCase(ChecklistTestCase):
	def setUp(self):
		super().setUp()
		self.other_tech = "_other-tech@deployops.test"
		frappe.get_doc(
			{
				"doctype": "User",
				"email": self.other_tech,
				"first_name": "Other",
				"send_welcome_email": 0,
				"roles": [{"role": TECHNICIAN}],
			}
		).insert(ignore_permissions=True)

	def as_tech(self, fn, *args, user=None):
		with set_user(user or self.technician):
			return fn(*args)


class TestHomeAndJobs(TechnicianApiTestCase):
	def test_me(self):
		info = self.as_tech(api.me)
		self.assertEqual((info["roles"], info["has_desk"]), (["Technician"], False))
		self.assertTrue(self.as_tech(api.me, user=self.supervisor)["has_desk"])
		outsider = "_outsider@deployops.test"
		frappe.get_doc(
			{"doctype": "User", "email": outsider, "first_name": "Out", "send_welcome_email": 0}
		).insert(ignore_permissions=True)
		with self.assertRaises(frappe.PermissionError):
			self.as_tech(api.me, user=outsider)

	def test_five_cards_with_my_open_job_counts(self):
		cards = self.as_tech(api.home)
		self.assertEqual([card["id"] for card in cards][:2], ["cashmatic-preinstall", CARD])
		self.assertFalse(any(card["open_jobs"] for card in cards))
		self.working_job()
		cards = {card["id"]: card for card in self.as_tech(api.home)}
		self.assertEqual((cards[CARD]["open_jobs"], cards["bellabot-onsite"]["open_jobs"]), (1, 0))
		self.assertEqual(
			{c["id"]: c["open_jobs"] for c in self.as_tech(api.home, user=self.other_tech)}[CARD], 0
		)

	def test_my_jobs_lists_only_my_open_jobs_for_the_card(self):
		job = self.working_job()
		result = self.as_tech(api.my_jobs, CARD)
		self.assertEqual(([row["name"] for row in result["jobs"]], result["jobs"][0]["machines"]), ([job], 1))
		self.assertEqual(self.as_tech(api.my_jobs, "bellabot-onsite")["jobs"], [])
		self.assertEqual(self.as_tech(api.my_jobs, CARD, user=self.other_tech)["jobs"], [])
		with self.assertRaises(frappe.DoesNotExistError):
			self.as_tech(api.my_jobs, "no-such-card")

	def test_job_view(self):
		job = self.working_job()
		view = self.as_tech(api.job_view, job)
		self.assertEqual((view["status"], view["customer_name"]), ("On Site", "_TestJobCust Ltd"))
		machine = view["machines"][0]
		self.assertEqual(
			(machine["serial_no"], machine["checklist"], machine["can_start_checklist"]),
			("JOB-CR-1", None, True),
		)
		with self.assertRaises(frappe.PermissionError):
			self.as_tech(api.job_view, job, user=self.other_tech)


class TestFormScreen(TechnicianApiTestCase):
	def setUp(self):
		super().setUp()
		self.job = self.working_job()
		self.name = self.start(self.job)

	def view(self, user=None):
		return self.as_tech(api.form_view, CASH_INSTALL, self.name, user=user)

	def save(self, values, user=None):
		return self.as_tech(api.save_form, CASH_INSTALL, self.name, values, user=user)

	def test_job_view_links_the_machine_form(self):
		machine = self.as_tech(api.job_view, self.job)["machines"][0]
		self.assertEqual(
			(machine["checklist"], machine["can_start_checklist"]),
			({"doctype": CASH_INSTALL, "name": self.name, "submitted": False}, False),
		)

	def test_form_view_describes_sections_and_fields(self):
		view = self.view()
		self.assertTrue(view["can_edit"])
		self.assertEqual(view["header"]["serial_no"], "JOB-CR-1")
		fields = {f["fieldname"]: f for s in view["sections"] for f in s["fields"]}
		self.assertEqual(fields["pos_brand"]["show"], {"field": "pos_integration", "value": "Yes"})
		self.assertTrue(fields["pos_brand"]["reqd"])
		self.assertEqual(fields["network_type"]["options"], ["Wi-Fi", "Ethernet cable"])
		self.assertEqual(
			(
				fields["installation_photos"]["table"]["kind"],
				fields["installation_photos"]["table"]["min_rows"],
			),
			("photos", 3),
		)
		self.assertTrue(next(s for s in view["sections"] if s["name"] == "warnings_section")["any_of"])
		self.assertNotIn("serial_no", fields)  # job data is in the header, not editable
		self.assertFalse(self.view(user=self.supervisor)["can_edit"])
		with self.assertRaises(frappe.PermissionError):
			self.view(user=self.other_tech)

	def test_device_comes_from_the_machine_and_is_read_only(self):
		doctype = "DeployOps Cashmatic Pre-installation"
		name = self.start(self.working_job("Pre-installation", serial="JOB-CR-2"))
		self.assertEqual(frappe.db.get_value(doctype, name, "device_model"), "_Test CR-460 name")
		self.as_tech(api.save_form, doctype, name, {"device_model": "Visual Pay 22 with stand"})
		self.assertEqual(frappe.db.get_value(doctype, name, "device_model"), "_Test CR-460 name")
		fields = {
			f["fieldname"]: f
			for s in self.as_tech(api.form_view, doctype, name)["sections"]
			for f in s["fields"]
		}
		self.assertTrue(fields["device_model"]["read_only"])

	def test_a_draft_header_shows_the_jobs_current_serial(self):
		doctype = "DeployOps Cashmatic Pre-installation"
		job = self.working_job("Pre-installation")  # undelivered order: no serial yet
		name = self.start(job)
		self.assertIsNone(self.as_tech(api.form_view, doctype, name)["header"]["serial_no"])
		with set_user(self.technician):
			job_doc = frappe.get_doc("DeployOps Job", job)
			job_doc.devices[0].serial_no = "JOB-CR-2"
			job_doc.save()
		self.assertEqual(self.as_tech(api.form_view, doctype, name)["header"]["serial_no"], "JOB-CR-2")

	def test_maintenance_tasks_are_a_fixed_grid(self):
		job = self.working_job("Maintenance", serial="JOB-CR-2")
		name = self.start(job)
		view = self.as_tech(api.form_view, MAINTENANCE, name)
		fields = {f["fieldname"]: f for s in view["sections"] for f in s["fields"]}
		self.assertEqual(fields["cashbox_tasks"]["table"]["kind"], "grid")
		rows = view["values"]["cashbox_tasks"]
		rows[0]["completed"] = "Yes"
		rows[0]["task"] = "Renamed"  # read only, ignored
		self.as_tech(api.save_form, MAINTENANCE, name, {"cashbox_tasks": rows})
		saved = frappe.get_doc(MAINTENANCE, name).cashbox_tasks[0]
		self.assertEqual((saved.task, saved.completed), ("Cleaning the cashbox and the NV200 chassis", "Yes"))

	def test_save_is_partial_and_checked(self):
		self.save({"network_type": "Wi-Fi"})
		self.save({"ip_address": "10.0.0.5", "serial_no": "HACKED", "step_security_cctv_coverage": 1})
		values = self.view()["values"]
		self.assertEqual(
			(values["network_type"], values["ip_address"], values["step_security_cctv_coverage"]),
			("Wi-Fi", "10.0.0.5", 1),
		)
		self.assertEqual(frappe.db.get_value(CASH_INSTALL, self.name, "serial_no"), "JOB-CR-1")
		photo = self.attach(CASH_INSTALL, self.name)[0]
		self.save(
			{
				"installation_photos": [{"image": photo, "caption": "Front"}],
				"keys_receiver_signature": VALID_SIGNATURE,
			}
		)
		self.assertEqual(self.view()["values"]["installation_photos"][0]["image"], photo)

		with self.assertRaises(frappe.ValidationError):
			self.save({"network_type": "4G"})
		with self.assertRaises(frappe.ValidationError):
			self.save({"ip_address": "pin: 1234"})
		with self.assertRaises(frappe.PermissionError):
			self.save({"ip_address": "x"}, user=self.supervisor)

	def test_submit(self):
		with self.assertRaises(frappe.ValidationError):
			self.as_tech(api.submit_form, CASH_INSTALL, self.name)
		with set_user(self.technician):
			self.complete(frappe.get_doc(CASH_INSTALL, self.name)).save()
		self.assertEqual(self.as_tech(api.submit_form, CASH_INSTALL, self.name), {"docstatus": 1})
		view = self.view()
		self.assertFalse(view["can_edit"])
		self.assertTrue(view["submitted_on"])
		self.assertTrue(self.as_tech(api.job_view, self.job)["machines"][0]["checklist"]["submitted"])

	def test_a_submitted_form_shows_its_snapshot(self):
		with set_user(self.technician):
			doc = self.complete(frappe.get_doc(CASH_INSTALL, self.name))
			doc.save()
			doc.submit()
		snapshot = frappe.parse_json(doc.submission_snapshot)
		snapshot["sections"][1]["label"] = "Question text from an older version"
		frappe.db.set_value(CASH_INSTALL, self.name, "submission_snapshot", frappe.as_json(snapshot))
		view = self.view()
		self.assertEqual(view["sections"][1]["label"], "Question text from an older version")
		self.assertEqual(view["form_version"], 1)
