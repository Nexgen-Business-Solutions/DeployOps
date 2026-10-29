from pathlib import Path

import frappe

from deployops.roles import DESK_ACCESS

PRE_INSTALLATION = "DeployOps Cashmatic Pre-installation"
# Bundled references (deployops/reference_files/) and where the pre-installation Jotform showed them.
BUNDLED_REFERENCES = (
	("user-manual.pdf", "Self Pay 460 user manual", "shared_documents_prior_to_the_visit_section"),
	("web-interface.pdf", "Web panel interface", "shared_documents_prior_to_the_visit_section"),
	("my-cashmatic-app.pdf", "My Cashmatic App", "shared_documents_prior_to_the_visit_section"),
	(
		"device-installation-guide.pdf",
		"Cashmatic Device Installation Guide (CDIG)",
		"machine_configuration_steps_section",
	),
	(
		"device-installation-guide.pdf",
		"Cashmatic Device Installation Guide (CDIG)",
		"machine_activation_steps_section",
	),
	("parts-manual.pdf", "Self Pay 460 parts (user manual)", "machine_activation_steps_section"),
	("device-configuration.pdf", "F1 client device configuration", "machine_configuration_steps_section"),
	("user-setup.pdf", "F2 user access configuration", "employee_checklist_section"),
	("logo.png", "Massarie logo (machine labeling)", "employee_checklist_section"),
)


def install_reference_files():
	"""Seed the bundled reference files once; administrators own the list afterwards (#42).

	Files missing from deployops/reference_files/ are skipped, so a fresh install without them
	simply starts with an empty list.
	"""
	settings = frappe.get_single("DeployOps Reference Files")
	if settings.references:
		return
	root = Path(frappe.get_app_path("deployops", "reference_files"))
	uploaded: dict[str, str] = {}
	for filename, title, section in BUNDLED_REFERENCES:
		path = root / filename
		if not path.is_file():
			continue
		if filename not in uploaded:
			uploaded[filename] = (
				frappe.get_doc(
					{
						"doctype": "File",
						"file_name": filename,
						"content": path.read_bytes(),
						"is_private": 1,
						"attached_to_doctype": settings.doctype,
						"attached_to_name": settings.name,
					}
				)
				.insert(ignore_permissions=True)
				.file_url
			)
		settings.append(
			"references",
			{"title": title, "file": uploaded[filename], "checklist": PRE_INSTALLATION, "section": section},
		)
	if settings.references:
		settings.save(ignore_permissions=True)


def create_roles():
	"""Create the DeployOps roles if they are missing, and keep their Desk access as designed.

	Runs before install and before every migrate, so any site with the app has the roles. Desk access
	is part of the security model (Technicians use only the app), so a role whose Desk access was
	changed on the site is set back, and its users' type (System / Website User) is recomputed.
	Other role settings are left as the site administrator configured them.
	"""
	corrected = []
	for role, desk_access in DESK_ACCESS.items():
		if not frappe.db.exists("Role", role):
			frappe.get_doc(
				{"doctype": "Role", "role_name": role, "desk_access": desk_access, "is_custom": 0}
			).insert(ignore_permissions=True)
		elif frappe.utils.cint(frappe.db.get_value("Role", role, "desk_access")) != desk_access:
			frappe.db.set_value("Role", role, "desk_access", desk_access)
			corrected.append(role)
			print(
				f"DeployOps: Desk access of role {role} was changed on this site; set back to {desk_access}."
			)
	if corrected:
		frappe.clear_cache()
		users = frappe.get_all(
			"Has Role", filters={"role": ["in", corrected], "parenttype": "User"}, pluck="parent"
		)
		for user in set(users):
			frappe.get_doc("User", user).save(ignore_permissions=True)  # recomputes the user type
