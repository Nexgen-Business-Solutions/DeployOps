"""DeployOps Cashmatic Maintenance checklist (source: https://form.jotform.com/253383306590256; field mapping pending #40 sign-off)."""

from typing import ClassVar

from deployops.checklists.form import ChecklistForm


class DeployOpsCashmaticMaintenance(ChecklistForm):
	FORM_VERSION = 1
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
