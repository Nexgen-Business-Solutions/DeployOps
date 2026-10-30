"""ERPNext source documents for tests, written straight to the database.

DeployOps only reads these records, so the tests store them in the exact state under test
(draft, submitted, closed, return…) without ERPNext's posting logic. That keeps the tests
independent of the site's accounting and stock setup, including a fresh CI site.
"""

import frappe

COMPANY = "_Test DeployOps Company"
OTHER_COMPANY = "_Test Other Company"


def db_insert(doc_dict: dict, docstatus: int = 0) -> "frappe.model.document.Document":
	doc = frappe.get_doc(doc_dict)
	doc.name = doc.name or frappe.generate_hash(length=10)
	doc.docstatus = docstatus
	doc.db_insert()
	for child in doc.get_all_children():
		child.parent, child.parenttype = doc.name, doc.doctype
		child.name = child.name or frappe.generate_hash(length=10)
		child.docstatus = docstatus
		child.db_insert()
	return doc


def make_company(name: str = COMPANY) -> str:
	"""A bare Company row so Link validation passes; no accounts are needed because nothing posts."""
	if not frappe.db.exists("Company", name):
		db_insert(
			{
				"doctype": "Company",
				"name": name,
				"company_name": name,
				"abbr": "".join(word[0] for word in name.split() if word[0].isalnum())[:5],
				"default_currency": "XAF",
				"country": "Cameroon",
			}
		)
	return name


def make_item(code: str, serialized: bool = True) -> str:
	if not frappe.db.exists("Item", code):
		db_insert(
			{
				"doctype": "Item",
				"name": code,
				"item_code": code,
				"item_name": f"{code} name",
				"item_group": "Products",
				"stock_uom": "Nos",
				"has_serial_no": int(serialized),
			}
		)
	return code


def make_customer(name: str, contact: str | None = None, address: str | None = None) -> str:
	if frappe.db.exists("Customer", name):
		return name
	db_insert(
		{
			"doctype": "Customer",
			"name": name,
			"customer_name": f"{name} Ltd",
			"customer_primary_contact": contact,
			"customer_primary_address": address,
		}
	)
	return name


def make_contact(name: str) -> str:
	if not frappe.db.exists("Contact", name):
		db_insert(
			{
				"doctype": "Contact",
				"name": name,
				"first_name": name,
				"full_name": name,
				"email_id": f"{name.lower()}@example.com",
			}
		)
	return name


def make_address(name: str) -> str:
	if not frappe.db.exists("Address", name):
		db_insert(
			{
				"doctype": "Address",
				"name": name,
				"address_title": name,
				"address_type": "Shipping",
				"address_line1": "1 Test Street",
				"city": "Douala",
				"country": "Cameroon",
			}
		)
	return name


def make_serial(serial_no: str, item_code: str, company: str = COMPANY, customer: str | None = None) -> str:
	"""In stock by default (Active, in a warehouse); delivered when a customer is given."""
	if not frappe.db.exists("Serial No", serial_no):
		db_insert(
			{
				"doctype": "Serial No",
				"name": serial_no,
				"serial_no": serial_no,
				"item_code": item_code,
				"company": company,
				"status": "Delivered" if customer else "Active",
				"warehouse": None if customer else "_Test Stores",
				"customer": customer,
			}
		)
	return serial_no


def make_bundle(item_code: str, serials: list[str], cancelled: bool = False) -> str:
	return db_insert(
		{
			"doctype": "Serial and Batch Bundle",
			"item_code": item_code,
			"company": COMPANY,
			"type_of_transaction": "Outward",
			"voucher_type": "Delivery Note",
			"is_cancelled": int(cancelled),
			"entries": [{"serial_no": s, "item_code": item_code, "qty": -1} for s in serials],
		},
		docstatus=1,
	).name


def make_sales_order(
	customer: str, items: list[str], docstatus: int = 1, status: str = "To Deliver", **extra
):
	return db_insert(
		{
			"doctype": "Sales Order",
			"customer": customer,
			"company": COMPANY,
			"status": status,
			"items": [{"item_code": code, "item_name": f"{code} name", "qty": 1} for code in items],
			**extra,
		},
		docstatus=docstatus,
	)


def make_preinstall_orders(customer: str, items: list[str], count: int = 1, **extra) -> list:
	"""Create ``count`` submitted Sales Orders for Pre-installation, cycling through ``items``."""
	return [make_sales_order(customer, [items[i % len(items)]], **extra) for i in range(count)]


def make_delivery_note(customer: str, rows: list[dict], docstatus: int = 1, is_return: int = 0, **extra):
	"""rows: [{"item_code": ..., "serial_no": "S1\\nS2"} or {"item_code": ..., "serial_and_batch_bundle": ...}]"""
	return db_insert(
		{
			"doctype": "Delivery Note",
			"customer": customer,
			"company": COMPANY,
			"status": "To Bill",
			"is_return": is_return,
			"items": [{"qty": 1, **row} for row in rows],
			**extra,
		},
		docstatus=docstatus,
	)


def make_subscription_plan(name: str = "_Test Rental Plan") -> str:
	if not frappe.db.exists("Subscription Plan", name):
		db_insert(
			{
				"doctype": "Subscription Plan",
				"name": name,
				"plan_name": name,
				"billing_interval": "Monthly",
				"billing_interval_count": 1,
				"price_determination": "Fixed Rate",
				"cost": 0,
				"currency": "XAF",
			}
		)
	return name


def make_subscription(customer: str, status: str = "Active", party_type: str = "Customer"):
	make_subscription_plan()
	return db_insert(
		{
			"doctype": "Subscription",
			"party_type": party_type,
			"party": customer,
			"company": COMPANY,
			"status": status,
			"plans": [{"plan": "_Test Rental Plan", "qty": 1}],
		}
	)


def make_maintenance_visit(customer: str, purposes: list[dict], docstatus: int = 0):
	return db_insert(
		{
			"doctype": "Maintenance Visit",
			"customer": customer,
			"company": COMPANY,
			"status": {0: "Draft", 1: "Submitted", 2: "Cancelled"}[docstatus],
			"purposes": purposes,
		},
		docstatus=docstatus,
	)


def make_maintenance_schedule(customer: str, rows: list[dict], docstatus: int = 1):
	return db_insert(
		{
			"doctype": "Maintenance Schedule",
			"customer": customer,
			"company": COMPANY,
			"status": {0: "Draft", 1: "Submitted", 2: "Cancelled"}[docstatus],
			"items": rows,
		},
		docstatus=docstatus,
	)


def purge(company: str = COMPANY, names: dict | None = None):
	"""Remove committed fixtures (HTTP tests must commit). Submitted rows are deleted directly.

	names: extra {doctype: [names]} to delete, e.g. Items, Users, Jobs, Files.
	"""
	children = {
		"Sales Order": ["Sales Order Item"],
		"Delivery Note": ["Delivery Note Item"],
		"Subscription": ["Subscription Plan Detail"],
		"Maintenance Visit": ["Maintenance Visit Purpose"],
		"Maintenance Schedule": ["Maintenance Schedule Item"],
		"Serial and Batch Bundle": ["Serial and Batch Entry"],
	}
	for parent, child_tables in children.items():
		parents = frappe.get_all(parent, filters={"company": company}, pluck="name")
		if parents:
			for child in child_tables:
				frappe.db.delete(child, {"parent": ["in", parents]})
			frappe.db.delete(parent, {"name": ["in", parents]})
	frappe.db.delete("Serial No", {"company": company})

	# Try every delete, so one failure cannot leave the rest behind; report failures at the end.
	failures = []
	for doctype, doc_names in (names or {}).items():
		for name in doc_names:
			if not frappe.db.exists(doctype, name):
				continue
			try:
				# File's on_trash removes the stored file, so it must run for Files.
				frappe.delete_doc(
					doctype, name, force=True, ignore_permissions=True, ignore_on_trash=doctype != "File"
				)
			except Exception as e:
				failures.append(f"{doctype} {name}: {e}")
	if frappe.db.exists("Company", company):
		frappe.db.delete("Company", {"name": company})
	if failures:
		raise AssertionError("Fixture cleanup failed:\n" + "\n".join(failures))
