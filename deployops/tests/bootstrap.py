"""Base records the tests need on a fresh site (CI), where ERPNext's setup wizard never ran.

Run by the ``before_tests`` hook. Each record is created only if missing, so on a configured site
(deployops.local) nothing changes.
"""

import frappe

COUNTRY = "Cameroon"


def before_tests():
	_ensure("UOM", "Nos", {"uom_name": "Nos", "must_be_whole_number": 1})
	_ensure("Item Group", "All Item Groups", {"item_group_name": "All Item Groups", "is_group": 1})
	_ensure(
		"Item Group",
		"Products",
		{"item_group_name": "Products", "parent_item_group": "All Item Groups", "is_group": 0},
	)
	if not frappe.db.exists("Address Template", {"is_default": 1}):
		# An empty template gets Frappe's default layout on save.
		frappe.get_doc({"doctype": "Address Template", "country": COUNTRY, "is_default": 1}).insert(
			ignore_permissions=True
		)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit - test bootstrap must outlive per-test rollbacks


def _ensure(doctype: str, name: str, values: dict):
	if not frappe.db.exists(doctype, name):
		frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True)
