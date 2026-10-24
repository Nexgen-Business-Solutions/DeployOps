"""The five checklist forms (#20 / #41): one native DocType per Jotform, one form per machine."""

import frappe
from frappe.tests.classes.context_managers import set_user
from frappe.utils import now_datetime, today

from deployops.api import checklists as checklist_api
from deployops.api import jobs as job_api
from deployops.checklists.cards import CARDS, FORM_DOCTYPES
from deployops.checklists.form import HEADER_FIELDS, condition_met
from deployops.roles import MANAGER
from deployops.tests import erpnext_fixtures as fx
from deployops.tests.test_job import JOB, JobTestCase, make_job
from deployops.tests.utils import make_role_user

CASH_INSTALL = "DeployOps Cashmatic Installation"
MAINTENANCE = "DeployOps Cashmatic Maintenance"
BELLABOT_INSTALL = "DeployOps BellaBot Installation"
CATEGORY = "DeployOps Equipment Category"
SIGNATURE = "data:image/png;base64,iVBORw0KGgo="
PHOTO = "DeployOps Checklist Photo"


class ChecklistTestCase(JobTestCase):
	def setUp(self):
		super().setUp()
		# Only the test categories decide product lines, whatever the site has configured.
		frappe.db.set_value(CATEGORY, {"name": ["is", "set"]}, "product_line", None)
		frappe.db.set_value(CATEGORY, "_Test Cash", "product_line", "Cashmatic")
		frappe.get_doc(
			{
				"doctype": CATEGORY,
				"category_name": "_Test Robot",
				"product_line": "BellaBot",
				"items": [{"item_code": self.robot}],
			}
		).insert(ignore_permissions=True)
		self.manager = make_role_user(MANAGER)
		for user in (self.technician, self.supervisor, self.manager):
			name = frappe.db.get_value("DeployOps Equipment Access Profile", {"user": user})
			profile = (
				frappe.get_doc("DeployOps Equipment Access Profile", name)
				if name
				else frappe.get_doc(
					{
						"doctype": "DeployOps Equipment Access Profile",
						"user": user,
						"categories": [{"category": "_Test Cash"}],
					}
				)
			)
			profile.append("categories", {"category": "_Test Robot"})
			profile.save(ignore_permissions=True)

	def working_job(self, job_type="Installation", item=None, serial="JOB-CR-1"):
		item = item or self.cash
		if job_type == "Installation":
			bundle = fx.make_bundle(item, [serial])
			note = fx.make_delivery_note(
				self.customer, [{"item_code": item, "serial_and_batch_bundle": bundle}]
			)
			job = make_job("Delivery Note", note.name, assigned_technician=self.technician).name
		elif job_type == "Maintenance":
			visit = fx.make_maintenance_visit(self.customer, [{"item_code": item, "serial_no": serial}]).name
			job = make_job(
				"Maintenance Visit", visit, job_type="Maintenance", assigned_technician=self.technician
			).name
		else:
			order = fx.make_sales_order(self.customer, [item]).name
			job = make_job(
				"Sales Order", order, job_type="Pre-installation", assigned_technician=self.technician
			).name
		with set_user(self.supervisor):
			job_api.job_action(job, "start")
		if job_type == "Installation":
			with set_user(self.technician):
				job_api.job_action(job, "arrive")
		return job

	def start(self, job, user=None):
		device = frappe.get_doc(JOB, job).devices[0].name
		with set_user(user or self.technician):
			return checklist_api.start_checklist(job, device)["name"]

	def attach(self, doctype, name, count=1):
		"""Private files attached to the form, as the app uploads them."""
		return [
			frappe.get_doc(
				{
					"doctype": "File",
					"file_name": f"{frappe.generate_hash(length=8)}.png",
					"is_private": 1,
					"content": frappe.generate_hash().encode(),
					"attached_to_doctype": doctype,
					"attached_to_name": name,
				}
			)
			.insert(ignore_permissions=True)
			.file_url
			for _ in range(count)
		]

	def complete(self, doc):
		"""Answer every required visible field and tick one box per "at least one" group."""
		for df in doc.meta.fields:
			if (
				df.hidden
				or df.read_only
				or df.fieldname in HEADER_FIELDS
				or not condition_met(doc, df.depends_on)
			):
				continue
			required = df.reqd or (df.mandatory_depends_on and condition_met(doc, df.mandatory_depends_on))
			if df.fieldtype == "Table":
				self.complete_table(doc, df, required)
			elif required:
				doc.set(df.fieldname, self.answer(df))
		for fields in doc.ANY_OF.values():
			doc.set(fields[0], 1)
		return doc

	def answer(self, df):
		if df.fieldtype == "Check":
			return 1
		if df.fieldtype == "Select":
			return df.options.split("\n")[1]
		return {
			"Date": today(),
			"Datetime": now_datetime(),
			"Time": "09:00:00",
			"Int": 70,
			"Float": 2,
			"Currency": 10,
			"Signature": SIGNATURE,
		}.get(df.fieldtype, "a@b.test" if df.options == "Email" else "Fine")

	def complete_table(self, doc, df, required):
		minimum = doc.MIN_ROWS.get(df.fieldname) or (1 if required else 0)
		if df.options in (PHOTO, "DeployOps Checklist File"):
			column = "image" if df.options == PHOTO else "file"
			doc.set(df.fieldname, [{column: url} for url in self.attach(doc.doctype, doc.name, minimum)])
			return
		child = frappe.get_meta(df.options)
		if df.fieldname not in doc.FIXED_ROWS:
			doc.set(df.fieldname, [{} for _ in range(minimum)])
		for row in doc.get(df.fieldname):
			for column in child.fields:
				if column.reqd and not column.read_only:
					row.set(column.fieldname, self.answer(column))
			if df.options == "DeployOps Checklist Opening Hours":
				row.update({"open_time": "08:00:00", "close_time": "18:00:00"})


class TestStartingAForm(ChecklistTestCase):
	def test_start_creates_the_form_for_the_machine_with_job_data(self):
		job = self.working_job()
		name = self.start(job)
		doc = frappe.get_doc(CASH_INSTALL, name)
		self.assertEqual(
			(doc.item_code, doc.serial_no, doc.customer_name, doc.technician),
			(self.cash, "JOB-CR-1", frappe.db.get_value(JOB, job, "customer_name"), self.technician),
		)

	def test_maintenance_form_gets_its_fixed_task_rows(self):
		doc = frappe.get_doc(MAINTENANCE, self.start(self.working_job("Maintenance")))
		self.assertEqual([row.task for row in doc.cashbox_tasks], list(doc.FIXED_ROWS["cashbox_tasks"][1]))
		with set_user(self.technician), self.assertRaises(frappe.ValidationError):
			doc.cashbox_tasks[0].task = "Something else"
			doc.save()

	def test_each_card_matches_job_type_and_product_line(self):
		cases = {
			("Pre-installation", self.cash): "DeployOps Cashmatic Pre-installation",
			("Installation", self.robot): BELLABOT_INSTALL,
			("Pre-installation", self.robot): "DeployOps BellaBot Pre-installation",
			("Maintenance", self.cash): MAINTENANCE,
		}
		for (job_type, item), doctype in cases.items():
			with self.subTest(job_type=job_type, item=item):
				job = self.working_job(job_type, item, "JOB-BB-1" if item == self.robot else "JOB-CR-2")
				device = frappe.get_doc(JOB, job).devices[0].name
				with set_user(self.technician):
					self.assertEqual(checklist_api.start_checklist(job, device)["doctype"], doctype)

	def test_refusals(self):
		job = self.working_job()
		device = frappe.get_doc(JOB, job).devices[0].name
		with set_user(self.technician):
			with self.assertRaises(frappe.ValidationError):  # wrong form for a cash machine
				frappe.get_doc({"doctype": BELLABOT_INSTALL, "job": job, "job_device": device}).insert()
			checklist_api.start_checklist(job, device)
			with self.assertRaises(frappe.ValidationError):  # one form per machine
				checklist_api.start_checklist(job, device)

		draft = make_job(
			"Delivery Note",
			fx.make_delivery_note(
				self.customer,
				[
					{
						"item_code": self.cash,
						"serial_and_batch_bundle": fx.make_bundle(self.cash, ["JOB-CR-2"]),
					}
				],
			).name,
			assigned_technician=self.technician,
		).name
		with set_user(self.technician), self.assertRaises(frappe.ValidationError):
			self.start(draft)  # job not started

		frappe.db.set_value(CATEGORY, "_Test Cash", "product_line", None)
		other = self.working_job(serial="JOB-CR-3")
		with set_user(self.technician), self.assertRaises(frappe.ValidationError):
			self.start(other)  # no product line, no form

	def test_supervisor_cannot_start_a_form(self):
		job = self.working_job()
		with self.assertRaises(frappe.PermissionError):
			self.start(job, user=self.supervisor)


class TestFilling(ChecklistTestCase):
	def setUp(self):
		super().setUp()
		self.name = self.start(self.working_job())

	def doc(self):
		return frappe.get_doc(CASH_INSTALL, self.name)

	def test_draft_saves_with_gaps_but_submit_lists_what_is_missing(self):
		with set_user(self.technician):
			doc = self.doc()
			doc.ip_address = "192.168.1.40"
			doc.save()
			missing = doc.missing()
			joined = "\n".join(missing)
			for text in (
				"not ticked",
				"Web panel explanation: tick at least one",
				"Photos of installation: at least 3",
				"Keys receiver signature: required",
				"POS integration: required",
			):
				self.assertIn(text, joined)
			with self.assertRaises(frappe.ValidationError):
				doc.submit()

	def test_condition_shows_and_requires_a_field(self):
		with set_user(self.technician):
			doc = self.complete(self.doc())
			doc.pos_integration = "No"
			doc.pos_brand = None
			doc.save()
			self.assertEqual(doc.missing(), [])
			doc.pos_integration = "Yes"
			self.assertIn("POS brand / version: required.", doc.missing())

	def test_complete_form_submits_and_locks(self):
		with set_user(self.technician):
			doc = self.complete(self.doc())
			doc.installation_photos = doc.installation_photos[:2]
			doc.save()
			self.assertIn("Photos of installation: at least 3 needed.", doc.missing())
			self.complete(doc).save()
			doc.submit()
			self.assertEqual(doc.docstatus, 1)
			with self.assertRaises(frappe.ValidationError):
				doc.remarks = "late change"
				doc.save()

	def test_version_is_stamped_and_a_snapshot_kept_on_submit(self):
		with set_user(self.technician):
			doc = self.complete(self.doc())
			self.assertEqual((doc.form_version, doc.submission_snapshot), (1, None))
			doc.save()
			doc.submit()
		snapshot = frappe.parse_json(frappe.db.get_value(CASH_INSTALL, self.name, "submission_snapshot"))
		labels = {f["fieldname"]: f["label"] for s in snapshot["sections"] for f in s["fields"]}
		self.assertEqual(
			(snapshot["form_version"], labels["ip_address"], snapshot["values"]["pos_integration"]),
			(1, "IP address", doc.pos_integration),
		)
		self.assertEqual(len(snapshot["values"]["installation_photos"]), 3)

	def test_signatures_record_signer_time_and_user(self):
		with set_user(self.technician):
			doc = self.complete(self.doc())
			doc.keys_receiver_name = "Alice Keys"
			doc.client_representative = "Bob Client"
			doc.client_signature = SIGNATURE
			doc.save()
			record = {row.signature_field: row for row in doc.signatures}
			self.assertEqual(
				(record["keys_receiver_signature"].signer_name, record["client_signature"].signer_name),
				("Alice Keys", "Bob Client"),
			)
			self.assertEqual(record["client_signature"].captured_by, self.technician)
			first = record["client_signature"].signed_on

			doc.signatures = []  # the record cannot be edited; it is rebuilt from the form
			doc.remarks = "unrelated change"
			doc.save()
			self.assertEqual(
				{row.signature_field: row.signed_on for row in doc.signatures}["client_signature"], first
			)

			doc.client_signature = None
			doc.save()
			self.assertNotIn("client_signature", [row.signature_field for row in doc.signatures])
			doc.submit()
		snapshot = frappe.parse_json(frappe.db.get_value(CASH_INSTALL, self.name, "submission_snapshot"))
		self.assertEqual(snapshot["signatures"]["keys_receiver_signature"]["signer_name"], "Alice Keys")

	def test_a_signature_needs_the_signer_name(self):
		with set_user(self.technician):
			doc = self.complete(self.doc())
			doc.client_signature = SIGNATURE
			doc.client_representative = None
			doc.save()
			self.assertIn("Client representative signature: the signer's name is required.", doc.missing())

	def test_a_form_started_on_an_older_version_cannot_be_submitted(self):
		frappe.db.set_value(CASH_INSTALL, self.name, "form_version", 0)
		with set_user(self.technician), self.assertRaises(frappe.ValidationError):
			doc = self.complete(self.doc())
			doc.save()
			doc.submit()

	def test_job_data_cannot_be_changed(self):
		with set_user(self.technician), self.assertRaises(frappe.ValidationError):
			doc = self.doc()
			doc.serial_no = "JOB-CR-2"
			doc.save()
		with set_user(self.technician), self.assertRaises(frappe.ValidationError):
			doc = self.doc()
			doc.submission_snapshot = '{"sections": []}'
			doc.save()

	def test_a_draft_follows_the_machines_serial_and_needs_one_to_submit(self):
		"""#22: the serial is assigned before preparation completes; a draft picks it up from the job."""
		preparation = "DeployOps Cashmatic Pre-installation"
		job = self.working_job("Pre-installation")  # an undelivered order: no serial picked yet
		name = self.start(job)
		with set_user(self.technician):
			doc = self.complete(frappe.get_doc(preparation, name))
			doc.save()
			self.assertIsNone(doc.serial_no)
			self.assertIn(
				"Serial number: assign the machine's serial number on the job first.", doc.missing()
			)
			with self.assertRaises(frappe.ValidationError):
				doc.submit()

		with set_user(self.technician):  # the technician picks the machine during preparation
			job_doc = frappe.get_doc(JOB, job)
			job_doc.devices[0].serial_no = "JOB-CR-2"
			job_doc.save()
			doc = frappe.get_doc(preparation, name)
			doc.save()
			self.assertEqual((doc.serial_no, doc.missing()), ("JOB-CR-2", []))
			doc.submit()
		self.assertEqual(frappe.db.get_value(preparation, name, "serial_no"), "JOB-CR-2")

	def test_secrets_foreign_files_and_bad_signatures_are_refused(self):
		other = self.attach("DeployOps Job", frappe.db.get_value(CASH_INSTALL, self.name, "job"))[0]
		cases = {
			"secret": lambda d: d.set("ip_address", "password: 1234"),
			"secret in a row": lambda d: d.append(
				"installation_photos",
				{"image": self.attach(CASH_INSTALL, self.name)[0], "caption": "PIN = 4455"},
			),
			"foreign file": lambda d: d.append("installation_photos", {"image": other}),
			"signature": lambda d: d.set("keys_receiver_signature", "javascript:alert(1)"),
		}
		for case, change in cases.items():
			with (
				self.subTest(case=case),
				set_user(self.technician),
				self.assertRaises(frappe.ValidationError),
			):
				doc = self.doc()
				change(doc)
				doc.save()


class TestEveryForm(ChecklistTestCase):
	def test_each_of_the_five_forms_can_be_completed_and_submitted(self):
		jobs = {
			"DeployOps Cashmatic Pre-installation": ("Pre-installation", self.cash, "JOB-CR-1"),
			CASH_INSTALL: ("Installation", self.cash, "JOB-CR-2"),
			"DeployOps BellaBot Pre-installation": ("Pre-installation", self.robot, "JOB-BB-1"),
			BELLABOT_INSTALL: ("Installation", self.robot, "JOB-BB-1"),
			MAINTENANCE: ("Maintenance", self.cash, "JOB-CR-3"),
		}
		self.assertEqual(set(jobs), set(FORM_DOCTYPES))
		for doctype, (job_type, item, serial) in jobs.items():
			with self.subTest(doctype=doctype):
				job = self.working_job(job_type, item, serial)
				name = self.start(job)
				with set_user(self.technician):
					if job_type == "Pre-installation":  # an undelivered order: pick the machine first (#22)
						job_doc = frappe.get_doc(JOB, job)
						job_doc.devices[0].serial_no = serial
						job_doc.save()
					doc = frappe.get_doc(doctype, name)
					self.assertTrue(doc.missing())
					self.complete(doc).save()
					self.assertEqual(doc.missing(), [])
					doc.submit()

	def test_cards_name_existing_submittable_doctypes(self):
		for card in CARDS:
			meta = frappe.get_meta(card["doctype"])
			self.assertTrue(meta.is_submittable)
			for df in meta.fields:
				if df.depends_on:
					condition_met(frappe.new_doc(card["doctype"]), df.depends_on)  # supported syntax


class TestAccess(ChecklistTestCase):
	def test_forms_follow_job_visibility(self):
		name = self.start(self.working_job())
		with set_user(self.supervisor):
			self.assertTrue(frappe.has_permission(CASH_INSTALL, "read", name))
		other = "_other-tech@deployops.test"
		frappe.get_doc(
			{
				"doctype": "User",
				"email": other,
				"first_name": "Other",
				"send_welcome_email": 0,
				"roles": [{"role": "DeployOps Technician"}],
			}
		).insert(ignore_permissions=True)
		with set_user(other):
			self.assertFalse(frappe.has_permission(CASH_INSTALL, "read", name))
			self.assertNotIn(name, frappe.get_list(CASH_INSTALL, pluck="name"))

	def test_evidence_files_follow_the_form(self):
		name = self.start(self.working_job())
		url = self.attach(CASH_INSTALL, name)[0]
		file = frappe.get_doc("File", {"file_url": url})
		other = "_other-tech@deployops.test"
		frappe.get_doc(
			{
				"doctype": "User",
				"email": other,
				"first_name": "Other",
				"send_welcome_email": 0,
				"roles": [{"role": "DeployOps Technician"}],
			}
		).insert(ignore_permissions=True)
		for user, allowed in (
			(self.technician, True),
			(self.supervisor, True),
			(other, False),
			("Guest", False),
		):
			with self.subTest(user=user):
				self.assertEqual(bool(frappe.has_permission("File", "read", file, user=user)), allowed)

	def test_manager_can_cancel_a_submitted_form(self):
		name = self.start(self.working_job())
		with set_user(self.technician):
			self.complete(frappe.get_doc(CASH_INSTALL, name)).save()
			frappe.get_doc(CASH_INSTALL, name).submit()
		with set_user(self.supervisor), self.assertRaises(frappe.PermissionError):
			checklist_api.cancel_checklist(CASH_INSTALL, name, "wrong machine")
		with set_user(self.manager):
			with self.assertRaises(frappe.ValidationError):
				checklist_api.cancel_checklist(CASH_INSTALL, name, " ")
			checklist_api.cancel_checklist(CASH_INSTALL, name, "Filled on the wrong machine")
		self.assertEqual(frappe.db.get_value(CASH_INSTALL, name, "docstatus"), 2)
