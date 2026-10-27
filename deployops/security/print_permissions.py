import frappe
from frappe import _


def check_print_permission(doc, method=None, print_settings=None):
	if frappe.flags.ignore_print_permissions:
		return
	if not frappe.has_permission(doc.doctype, "print", doc):
		frappe.throw(
			_("You are not permitted to print {0} {1}.").format(_(doc.doctype), doc.name),
			frappe.PermissionError,
		)
