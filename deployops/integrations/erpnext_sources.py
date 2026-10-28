"""Read-only ERPNext source lookups and validation

DeployOps never writes ERPNext records. These functions read them server side (DeployOps roles
have no direct ERPNext permissions), check that a record is a usable source, and return only the
fields DeployOps needs. Equipment-profile filtering happens in deployops.api.sources.
"""

import frappe
from erpnext.stock.doctype.serial_no.serial_no import get_serial_nos
from frappe import _
from frappe.contacts.doctype.address.address import render_address

from deployops.security.company_access import allowed_companies

SALES_ORDER = "Sales Order"
DELIVERY_NOTE = "Delivery Note"
SUBSCRIPTION = "Subscription"
MAINTENANCE_VISIT = "Maintenance Visit"
MAINTENANCE_SCHEDULE = "Maintenance Schedule"

SOURCE_DOCTYPES = (SALES_ORDER, DELIVERY_NOTE, SUBSCRIPTION, MAINTENANCE_VISIT, MAINTENANCE_SCHEDULE)


def validate_source(doctype: str, name: str, company: str | None = None):
	"""Return the source document if DeployOps may use it, otherwise raise a clear error."""
	if doctype not in SOURCE_DOCTYPES:
		frappe.throw(_("{0} is not a DeployOps source document.").format(doctype))

	if not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(_(doctype), name), frappe.DoesNotExistError)

	doc = frappe.get_doc(doctype, name)
	reason = state_problem(doc)
	if reason:
		frappe.throw(_("{0} {1} cannot be used: {2}").format(_(doctype), name, reason))

	companies = allowed_companies(doctype)
	if companies is not None and doc.company not in companies:
		frappe.throw(
			_("You are not allowed to use sources of company {0}.").format(doc.company),
			frappe.PermissionError,
		)

	if company and doc.company != company:
		frappe.throw(
			_("{0} {1} belongs to company {2}, not {3}.").format(_(doctype), name, doc.company, company)
		)

	return doc


def state_problem(doc) -> str | None:
	if doc.doctype == SALES_ORDER:
		if doc.docstatus != 1:
			return _("it is not submitted")
		if doc.status in ("Closed", "On Hold", "Cancelled"):
			return _("its status is {0}").format(_(doc.status))

	elif doc.doctype == DELIVERY_NOTE:
		if doc.docstatus != 1:
			return _("it is not submitted")
		if doc.is_return:
			return _("it is a return")

	elif doc.doctype == SUBSCRIPTION:
		if doc.party_type != "Customer":
			return _("it is not a customer subscription")
		if doc.status in ("Cancelled", "Completed"):
			return _("its status is {0}").format(_(doc.status))

	elif doc.doctype == MAINTENANCE_VISIT:
		if doc.docstatus == 2:
			return _("it is cancelled")

	elif doc.doctype == MAINTENANCE_SCHEDULE:
		if doc.docstatus != 1:
			return _("it is not submitted")

	return None


def get_customer(doc) -> str | None:
	return doc.party if doc.doctype == SUBSCRIPTION else doc.get("customer")


def get_equipment_lines(doc) -> list[dict]:
	"""Item lines with their serial numbers, in the order they appear on the source.

	A Subscription bills service plans; the physical device is allocated separately, so it
	returns no equipment lines and nothing is inferred from its plans.
	"""
	if doc.doctype in (SALES_ORDER, DELIVERY_NOTE):
		rows = doc.items
	elif doc.doctype == MAINTENANCE_VISIT:
		rows = doc.purposes
	elif doc.doctype == MAINTENANCE_SCHEDULE:
		rows = doc.items
	else:
		return []

	return [
		{
			"item_code": row.item_code,
			"item_name": row.get("item_name"),
			"qty": row.get("qty"),
			"serial_nos": get_row_serials(row),
		}
		for row in rows
	]


def get_row_serials(row) -> list[str]:
	"""Serials on a row: Serial and Batch Bundle entries first, else the older serial_no text."""
	bundle = row.get("serial_and_batch_bundle")
	if bundle and not frappe.db.get_value("Serial and Batch Bundle", bundle, "is_cancelled"):
		serials = frappe.get_all(
			"Serial and Batch Entry",
			filters={"parent": bundle, "parenttype": "Serial and Batch Bundle"},
			pluck="serial_no",
			order_by="idx",
		)
		return [s for s in serials if s]

	return get_serial_nos(row.get("serial_no") or "")


def delivery_orders(delivery_note: str) -> set[str]:
	"""Sales orders a Delivery Note delivers against."""
	return set(
		frappe.get_all(
			"Delivery Note Item",
			filters={
				"parent": delivery_note,
				"parenttype": DELIVERY_NOTE,
				"against_sales_order": ["is", "set"],
			},
			pluck="against_sales_order",
		)
	)


def get_contact(doc) -> dict | None:
	name = doc.get("contact_person")
	customer = get_customer(doc)
	if not name and customer:
		name = frappe.db.get_value("Customer", customer, "customer_primary_contact")
	if not name:
		return None

	contact = frappe.db.get_value(
		"Contact", name, ["name", "full_name", "email_id", "phone", "mobile_no"], as_dict=True
	)
	return dict(contact) if contact else None


def get_address(doc) -> dict | None:
	name = doc.get("shipping_address_name") or doc.get("customer_address")
	customer = get_customer(doc)
	if not name and customer:
		name = frappe.db.get_value("Customer", customer, "customer_primary_address")
	if not name or not frappe.db.exists("Address", name):
		return None

	return {"name": name, "display": render_address(name, check_permissions=False)}


def get_source_snapshot(doc) -> dict:
	"""Identifying data of a validated source, for display and for storing on a Job (#18)."""
	customer = get_customer(doc)
	return {
		"doctype": doc.doctype,
		"name": doc.name,
		"company": doc.company,
		"status": doc.get("status"),
		"docstatus": doc.docstatus,
		"customer": customer,
		"customer_name": frappe.db.get_value("Customer", customer, "customer_name") if customer else None,
		"contact": get_contact(doc),
		"address": get_address(doc),
		"lines": get_equipment_lines(doc),
		"plans": [row.plan for row in doc.plans] if doc.doctype == SUBSCRIPTION else [],
	}


def validate_serial(serial_no: str, item_code: str | None = None, company: str | None = None):
	"""Return the Serial No if it exists, matches the Item and belongs to the company.

	The caller's Company user permissions apply whatever `company` is passed (or not): a serial of a
	company outside them is refused, like a source document (#13 review).
	"""
	if not frappe.db.exists("Serial No", serial_no):
		frappe.throw(_("Serial No {0} does not exist.").format(serial_no), frappe.DoesNotExistError)

	serial = frappe.db.get_value(
		"Serial No",
		serial_no,
		[
			"name",
			"item_code",
			"item_name",
			"status",
			"company",
			"warehouse",
			"customer",
			"warranty_expiry_date",
		],
		as_dict=True,
	)
	if item_code and serial.item_code != item_code:
		frappe.throw(
			_("Serial No {0} belongs to Item {1}, not {2}.").format(serial_no, serial.item_code, item_code)
		)
	companies = allowed_companies("Serial No")
	if companies is not None and serial.company not in companies:
		frappe.throw(
			_("You are not allowed to use serials of company {0}.").format(serial.company or _("(none)")),
			frappe.PermissionError,
		)
	if company and serial.company and serial.company != company:
		frappe.throw(
			_("Serial No {0} belongs to company {1}, not {2}.").format(serial_no, serial.company, company)
		)

	return serial


def get_delivered_serials(sales_order: str) -> dict[str, list[str]]:
	"""Serials delivered against a Sales Order, per Item, minus any returned since.

	Read from submitted Delivery Notes made from the order; returns are subtracted.
	"""
	notes = frappe.get_all(
		"Delivery Note Item",
		filters={"against_sales_order": sales_order, "docstatus": 1},
		pluck="parent",
		distinct=True,
	)
	notes = frappe.get_all(
		"Delivery Note", filters={"name": ["in", notes or [""]], "is_return": 0}, pluck="name"
	)
	if not notes:
		return {}

	returned = set()
	for name in frappe.get_all(
		"Delivery Note",
		filters={"return_against": ["in", notes], "is_return": 1, "docstatus": 1},
		pluck="name",
	):
		for line in get_equipment_lines(frappe.get_doc(DELIVERY_NOTE, name)):
			returned.update(line["serial_nos"])

	delivered: dict[str, list[str]] = {}
	for name in notes:
		for line in get_equipment_lines(frappe.get_doc(DELIVERY_NOTE, name)):
			serials = [s for s in line["serial_nos"] if s not in returned]
			delivered.setdefault(line["item_code"], []).extend(serials)
	return delivered
