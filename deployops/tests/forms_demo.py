"""Idempotent synthetic data for the v2 technician screen, on a non-production site.

Uses fixture inserts: the Delivery Note is submitted without stock/accounting posting,
just as in integration tests. The job is set On Site without workflow history on purpose.
No commit here; bench execute owns the transaction.
"""

import json

import frappe
from forms_core import versions
from frappe import _
from frappe.tests.classes.context_managers import set_user

from deployops.api.forms import start_machine_form
from deployops.roles import TECHNICIAN
from deployops.tests import erpnext_fixtures as fx
from deployops.tests.forms_utils import JOB, RULE, add_rule
from deployops.tests.test_job import make_job

DEMO_USER = "demo.technician@example.com"


def definition() -> dict:
	def field(n, key, kind, label, **kwargs):
		return {"id": f"f_demo{n:02}", "key": key, "type": kind, "label": label, **kwargs}

	def condition(value):
		return {"field": "f_demo05", "op": "eq", "value": value}

	return {
		"schema": 1,
		"sections": [
			{
				"id": "s_demo01",
				"title": "Machine",
				"fields": [
					field(1, "serial", "text", "Serial", fill_from={"value": "serial_no", "locked": True}),
					field(2, "customer", "text", "Customer", fill_from={"value": "customer_name"}),
					field(3, "note", "info", "Note", config={"text": "Demo only. Never enter credentials."}),
				],
			},
			{
				"id": "s_demo02",
				"title": "Checks",
				"fields": [
					field(4, "area_safe", "checkbox", "Area safe", config={"must_tick": True}),
					field(
						5,
						"power",
						"yes_no",
						"Power",
						required=True,
						outcomes=[{"when": condition("No"), "effect": "block_machine"}],
					),
					field(
						6, "no_power_reason", "long_text", "No power reason", required_when=condition("No")
					),
					field(
						7,
						"mounting",
						"choice",
						"Mounting",
						config={"options": ["Counter", "Stand"], "display": "buttons", "allow_other": True},
					),
					field(
						8,
						"accessories",
						"multi_check",
						"Accessories",
						config={"options": ["Cable", "Manual"], "min_selected": 1, "allow_other": True},
					),
					field(9, "cables", "number", "Cables", config={"decimal": False, "min": 0, "max": 10}),
					field(10, "deposit", "currency", "Deposit"),
					field(11, "install_date", "date", "Install date"),
					field(12, "start_time", "time", "Start time"),
					field(13, "finished_at", "datetime", "Finished at"),
				],
			},
			{
				"id": "s_demo03",
				"title": "Opening hours",
				"show": condition("Yes"),
				"fields": [
					field(
						14,
						"hours",
						"table",
						"Hours",
						config={
							"columns": [
								{"id": "f_demc01", "type": "text", "label": "Day"},
								{"id": "f_demc02", "type": "time", "label": "Open"},
								{"id": "f_demc03", "type": "time", "label": "Close"},
								{"id": "f_demc04", "type": "checkbox", "label": "Closed"},
							],
							"fixed_rows": {
								"column": "f_demc01",
								"labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
							},
						},
					),
					field(
						15,
						"trainees",
						"table",
						"Trainees",
						config={
							"min_rows": 1,
							"columns": [
								{"id": "f_demc05", "type": "text", "label": "Name", "required": True},
								{
									"id": "f_demc06",
									"type": "choice",
									"label": "Role",
									"config": {"options": ["Operator", "Supervisor"]},
								},
							],
						},
					),
				],
			},
			{
				"id": "s_demo04",
				"title": "Evidence",
				"fields": [
					field(16, "photos", "photos", "Photos", config={"min": 1, "captions": True}),
					field(17, "documents", "files", "Documents", config={"extensions": ["pdf"]}),
					field(18, "customer_signer", "text", "Customer signer", required=True),
					field(
						19,
						"customer_signature",
						"signature",
						"Customer signature",
						config={"signer_from": "f_demo18"},
					),
					field(
						20,
						"technician_signature",
						"signature",
						"Technician signature",
						config={"signer_from": "context:technician"},
					),
				],
			},
		],
	}


def seed(technician: str = DEMO_USER) -> dict:
	"""Create/reuse two demo machines, a form and job, and open machine one's draft."""
	with set_user("Administrator"):
		if not frappe.db.exists("User", technician):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": technician,
					"first_name": _("Demo Technician"),
					"send_welcome_email": 0,
					"roles": [{"role": TECHNICIAN}],
				}
			).insert(ignore_permissions=True)
		if TECHNICIAN not in frappe.get_roles(technician):
			frappe.throw(_("The demo user must have the Technician role."))
		fx.make_company()
		item = fx.make_item("DEMO-MACHINE")
		category = "Demo Equipment"
		if not frappe.db.exists("DeployOps Equipment Category", category):
			frappe.get_doc(
				{
					"doctype": "DeployOps Equipment Category",
					"category_name": category,
					"items": [{"item_code": item}],
				}
			).insert(ignore_permissions=True)
		profile = frappe.db.get_value("DeployOps Equipment Access Profile", {"user": technician})
		profile = (
			frappe.get_doc("DeployOps Equipment Access Profile", profile)
			if profile
			else frappe.get_doc({"doctype": "DeployOps Equipment Access Profile", "user": technician})
		)
		if category not in {r.category for r in profile.categories}:
			profile.append("categories", {"category": category})
			profile.save(ignore_permissions=True)
		customer = fx.make_customer(
			"Demo Customer", fx.make_contact("Demo Contact"), fx.make_address("Demo Address")
		)
		for serial in ("DEMO-SN-1", "DEMO-SN-2"):
			fx.make_serial(serial, item, customer=customer)
		form = frappe.db.get_value("Form", {"key": "demo-all-fields"})
		if not form:
			form = (
				frappe.get_doc(
					{
						"doctype": "Form",
						"key": "demo-all-fields",
						"title": _("Demo all fields"),
						"context_doctype": JOB,
						"draft_definition": json.dumps(definition()),
					}
				)
				.insert()
				.name
			)
		if not frappe.db.get_value("Form", form, "current_version"):
			versions.publish(form)
		if not frappe.db.exists(
			RULE, {"job_type": "Installation", "equipment_category": category, "form": form}
		):
			add_rule("Installation", category, form)
		note_name = "DEMO-FORMS-DELIVERY"
		job_name = frappe.db.get_value(JOB, {"source_doctype": "Delivery Note", "source_name": note_name})
		if not job_name:
			if not frappe.db.exists("Delivery Note", note_name):
				fx.make_delivery_note(
					customer,
					[{"item_code": item, "qty": 2, "serial_no": "DEMO-SN-1\nDEMO-SN-2"}],
					name=note_name,
				)
			job_name = make_job("Delivery Note", note_name, assigned_technician=technician).name
			frappe.db.set_value(JOB, job_name, "status", "On Site")
		job = frappe.get_doc(JOB, job_name)
		if job.assigned_technician != technician:
			frappe.throw(_("The demo job is already assigned to another technician."))
		rows = [r.name for r in sorted(job.devices, key=lambda r: r.serial_no)]
	with set_user(technician):
		submission = start_machine_form(job_name, rows[0], form)["submission"]
	return {
		"form": form,
		"job": job_name,
		"rows": rows,
		"submission": submission,
		"url": f"http://localhost:8004/deployops/job/{job_name}",
		"submission_url": f"http://localhost:8004/deployops/s/{submission}",
		"login": technician,
	}
