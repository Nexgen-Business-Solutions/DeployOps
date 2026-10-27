import frappe
from frappe import _

no_cache = 1
APP_BASE = "/deployops"


def get_context():
	"""Serve the React app shell.

	Guests get the shell too, so the app can show its own login screen. The shell carries no
	business data: everything comes from API calls, which refuse guests (deny by default).
	"""
	# Served elsewhere only as a technician's home page (role_home_page, e.g. at "/"): the app's
	# routes live under /deployops, so go there. 302: "/" is redirected for technicians only, and
	# browsers cache a 301 for every user of that browser.
	path = frappe.request.path if getattr(frappe, "request", None) else APP_BASE
	if path != APP_BASE and not path.startswith(APP_BASE + "/"):
		frappe.flags.redirect_location = APP_BASE
		raise frappe.Redirect(302)

	context = frappe._dict()
	context.csrf_token = frappe.sessions.get_csrf_token() if frappe.session.user != "Guest" else ""
	context.is_guest = frappe.session.user == "Guest"
	return context


@frappe.whitelist(methods=["POST"])
def get_context_for_dev():
	if not frappe.conf.developer_mode:
		frappe.throw(_("This method is only meant for developer mode"))
	return {"site_name": frappe.local.site}
