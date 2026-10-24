"""Company scope for ERPNext sources: Frappe User Permissions on Company (owner decision, 2026-10-20).

A user with no Company user permission sees every company. A user with Company user permissions
(for all DocTypes, or for the source's DocType) only sees sources in those companies.
"""

import frappe


def allowed_companies(doctype: str, user: str | None = None) -> set[str] | None:
	"""Companies the user may use sources of this DocType from; None means no restriction."""
	user = user or frappe.session.user
	entries = frappe.permissions.get_user_permissions(user).get("Company") or []
	companies = {e["doc"] for e in entries if not e.get("applicable_for") or e["applicable_for"] == doctype}
	return companies or None
