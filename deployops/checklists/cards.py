"""The five checklist cards on the technician home screen (fixed, approved 2026-10-19).

Each card is one checklist DocType. A machine uses the card that matches its job type and the
product line of its equipment category (DeployOps Equipment Category → Checklist product line).
"""

import frappe

from deployops.security.equipment_access import get_category_items

CATEGORY = "DeployOps Equipment Category"

CARDS = (
	{
		"id": "cashmatic-preinstall",
		"title": "Cashmatic Pre-installation",
		"subtitle": "Prepare the machine before the visit",
		"job_type": "Pre-installation",
		"product_line": "Cashmatic",
		"doctype": "DeployOps Cashmatic Pre-installation",
		"icon": "clipboard-check",
	},
	{
		"id": "cashmatic-onsite",
		"title": "Cashmatic Installation",
		"subtitle": "Install and hand over at the customer",
		"job_type": "Installation",
		"product_line": "Cashmatic",
		"doctype": "DeployOps Cashmatic Installation",
		"icon": "wrench",
	},
	{
		"id": "bellabot-preinstall",
		"title": "BellaBot Pre-installation",
		"subtitle": "Site survey and GO / NO GO",
		"job_type": "Pre-installation",
		"product_line": "BellaBot",
		"doctype": "DeployOps BellaBot Pre-installation",
		"icon": "map",
	},
	{
		"id": "bellabot-onsite",
		"title": "BellaBot Installation",
		"subtitle": "Map, test and hand over the robot",
		"job_type": "Installation",
		"product_line": "BellaBot",
		"doctype": "DeployOps BellaBot Installation",
		"icon": "bot",
	},
	{
		"id": "cashmatic-maintenance",
		"title": "Cashmatic Maintenance",
		"subtitle": "Clean and inspect components",
		"job_type": "Maintenance",
		"product_line": "Cashmatic",
		"doctype": "DeployOps Cashmatic Maintenance",
		"icon": "settings",
	},
)

CARDS_BY_ID = {card["id"]: card for card in CARDS}
FORM_DOCTYPES = tuple(card["doctype"] for card in CARDS)


def items_by_product_line() -> dict[str, set[str]]:
	"""Machine models per product line, from the equipment categories that name one."""
	lines: dict[str, set[str]] = {}
	for category in frappe.get_all(
		CATEGORY, filters={"product_line": ["is", "set"], "enabled": 1}, fields=["name", "product_line"]
	):
		lines.setdefault(category.product_line, set()).update(get_category_items([category.name]))
	return lines


def card_for(job_type: str, item_code: str) -> dict | None:
	"""The card (checklist) for one machine on a job of this type; None when no single one fits."""
	lines = {line for line, items in items_by_product_line().items() if item_code in items}
	if len(lines) != 1:
		return None
	line = lines.pop()
	return next(
		(card for card in CARDS if card["job_type"] == job_type and card["product_line"] == line), None
	)


def form_for_device(job: str, device: str):
	"""The live (draft or submitted) checklist of one machine row, as (doctype, name, docstatus)."""
	for doctype in FORM_DOCTYPES:
		row = frappe.db.get_value(
			doctype,
			{"job": job, "job_device": device, "docstatus": ["!=", 2]},
			["name", "docstatus"],
			as_dict=True,
		)
		if row:
			return doctype, row.name, row.docstatus
	return None
