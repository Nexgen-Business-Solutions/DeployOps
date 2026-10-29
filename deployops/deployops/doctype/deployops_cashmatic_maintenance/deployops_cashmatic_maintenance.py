"""DeployOps Cashmatic Maintenance checklist (source: https://form.jotform.com/253383306590256; field mapping pending #40 sign-off)."""

from typing import ClassVar

import frappe

from deployops.checklists.form import ChecklistForm


class DeployOpsCashmaticMaintenance(ChecklistForm):
	FORM_VERSION = 1
	SIGNERS: ClassVar[dict] = {
		"technician_signature": "technician",
		"customer_signature": "customer_signatory",
	}
	FIXED_ROWS: ClassVar[dict] = {
		"cashbox_tasks": (
			"task",
			(
				"Cleaning the cashbox and the NV200 chassis",
				"Cashbox cleaning",
				"Cashbox functionality check",
				"Component assembly and insertion",
			),
		),
		"recycler_tasks": (
			"task",
			(
				"NVS200 head removal",
				"Cleaning the rubber rollers",
				"Internal rollers cleaning",
				"Cleaning the banknote recycler (PayOut)",
				"PayOut roller cleaning",
			),
		),
		"pelicano_tasks": (
			"task",
			(
				"Pelicano removal",
				"Coin disk cleaning",
				"Validation sensor cleaning",
				"Drive wheel cleaning",
				"Final cleaning",
				"Pelicano reassembly",
				"Pelicano startup (connect inside the Self Pay)",
			),
		),
		"hopper_tasks": (
			"task",
			(
				"Removing the Smart Hopper",
				"Cleaning the front sensors",
				"Light pipe tightening check",
				"Cleaning the dispensing solenoid",
				"Cleaning inside the solenoid",
				"Solenoid lubrication",
				"Belt / wheel synchronization check",
				"Belt tooth inspection",
				"Reassembling the Smart Hopper",
			),
		),
	}
	INTRO = "Maintenance of the four main internal components: banknote recycler / NVS200, cashbox, Pelicano coin acceptor and Smart Hopper."

	def before_insert(self):
		super().before_insert()
		job = frappe.get_doc("DeployOps Job", self.job)
		if job.source_doctype == "Maintenance Visit":
			self.maintenance_visit = job.source_name
			self.maintenance_schedule = frappe.db.get_value(
				"Maintenance Visit", job.source_name, "maintenance_schedule"
			)
		elif job.source_doctype == "Maintenance Schedule":
			self.maintenance_schedule = job.source_name
