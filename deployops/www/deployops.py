import frappe
from frappe import _

no_cache = 1


def get_context():
	"""Serve the React app shell.

	Guests get the shell too, so the app can show its own login screen. The shell carries no
	business data: everything comes from API calls, which refuse guests (deny by default).
	"""
	context = frappe._dict()
	context.csrf_token = frappe.sessions.get_csrf_token() if frappe.session.user != "Guest" else ""
	context.is_guest = frappe.session.user == "Guest"
	return context


@frappe.whitelist(methods=["POST"])
def get_context_for_dev():
	if not frappe.conf.developer_mode:
		frappe.throw(_("This method is only meant for developer mode"))
	return {"site_name": frappe.local.site}
