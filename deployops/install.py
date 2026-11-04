import json
from pathlib import Path

import frappe

from deployops.roles import DESK_ACCESS

REFERENCE_SETTINGS = "DeployOps Reference Files"
REFERENCE_SAVEPOINT = "deployops_reference_files"
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
INSTALLATION = "DeployOps Cashmatic Installation"
# The same, for the on-site Jotform.
INSTALLATION_REFERENCES = (
	(
		"device-installation-guide.pdf",
		"Cashmatic Device Installation Guide (CDIG)",
		"machine_positioning_evaluation_section",
	),
	(
		"device-installation-guide.pdf",
		"Cashmatic Device Installation Guide (CDIG)",
		"power_and_network_section",
	),
	("web-interface.pdf", "Web panel interface", "web_panel_explanation_section"),
	("my-cashmatic-app.pdf", "My Cashmatic App", "web_panel_explanation_section"),
	("warnings-precautions.pdf", "Warnings and precautions", "warnings_section"),
)
BELLABOT_PRE_INSTALLATION = "DeployOps BellaBot Pre-installation"
# The same, for the BellaBot pre-installation Jotform.
BELLABOT_PRE_INSTALLATION_REFERENCES = (
	(
		"bellabot-deployment-manual.pdf",
		"BellaBot Pro deployment manual",
		"documents_shared_before_installation_section",
	),
	(
		"bellabot-operation-guide.pdf",
		"BellaBot Pro operation guide",
		"documents_shared_before_installation_section",
	),
	(
		"bellabot-product-introduction.pdf",
		"BellaBot Pro product introduction",
		"documents_shared_before_installation_section",
	),
	(
		"bellabot-maintenance-and-care.png",
		"BellaBot Pro maintenance and care",
		"documents_shared_before_installation_section",
	),
)
BELLABOT_INSTALLATION = "DeployOps BellaBot Installation"
# The same, for the BellaBot on-site Jotform.
BELLABOT_INSTALLATION_REFERENCES = (
	(
		"bellabot-deployment-manual.pdf",
		"BellaBot Pro deployment manual",
		"mapping_and_positioning_section",
	),
	("bellabot-operation-guide.pdf", "BellaBot Pro operation guide", "modes_section"),
	(
		"bellabot-maintenance-and-care.png",
		"BellaBot Pro maintenance and care",
		"advisories_section",
	),
)


def bundled_references() -> list[tuple[str, str, str, str]]:
	"""Every bundled reference as (checklist, filename, title, section)."""
	rows = [(PRE_INSTALLATION, *row) for row in BUNDLED_REFERENCES]
	rows += [(INSTALLATION, *row) for row in INSTALLATION_REFERENCES]
	rows += [(BELLABOT_PRE_INSTALLATION, *row) for row in BELLABOT_PRE_INSTALLATION_REFERENCES]
	rows += [(BELLABOT_INSTALLATION, *row) for row in BELLABOT_INSTALLATION_REFERENCES]
	return rows


def sync_reference_files():
	"""Add each bundled reference file once per site, after install and after every migrate (#42).

	A site that already has the app gets the references of a new release on its next migrate.
	Administrators own the list: what was added is remembered in ``seeded_references``, so a row
	they delete is not added again. A row already listed (same checklist and section, with the same
	title or file) only counts as added. Files missing from deployops/reference_files/ are skipped
	until they are bundled.
	"""
	settings = frappe.get_single(REFERENCE_SETTINGS)
	seeded = set(json.loads(settings.seeded_references or "[]"))
	root = Path(frappe.get_app_path("deployops", "reference_files"))
	uploaded: dict[str, str] = {}
	changed = False
	for checklist, filename, title, section in bundled_references():
		key = f"{checklist}|{section}|{filename}"
		path = root / filename
		if key in seeded or not path.is_file():
			continue
		seeded.add(key)
		changed = True
		if _already_listed(settings, checklist, section, title, filename):
			continue
		if filename not in uploaded:
			uploaded[filename] = _upload(settings, filename, path)
		settings.append(
			"references",
			{"title": title, "file": uploaded[filename], "checklist": checklist, "section": section},
		)
	if changed:
		settings.seeded_references = json.dumps(sorted(seeded), indent=1)
		settings.save(ignore_permissions=True)


def sync_reference_files_after_migrate():
	"""The same after every migrate, but a problem never stops the migrate.

	Saving checks every row of the list, the administrator's too: a row whose file or section no
	longer exists would otherwise fail the whole migrate. Instead nothing is added, the error is in
	the Error Log, and the next migrate tries again once the list is fixed.
	"""
	frappe.db.savepoint(REFERENCE_SAVEPOINT)
	try:
		sync_reference_files()
	except Exception:
		frappe.db.rollback(save_point=REFERENCE_SAVEPOINT)
		frappe.log_error(title="DeployOps: bundled reference files not added")
		print("DeployOps: bundled reference files were not added; see the Error Log.")


def _already_listed(settings, checklist, section, title, filename) -> bool:
	return any(
		row.checklist == checklist
		and (row.section or "") == section
		and (row.title == title or (row.file or "").rsplit("/", 1)[-1] == filename)
		for row in settings.references
	)


def _upload(settings, filename: str, path: Path) -> str:
	"""The private copy of a bundled file attached to the settings, uploaded if it isn't yet."""
	existing = frappe.db.get_value(
		"File",
		{"attached_to_doctype": settings.doctype, "attached_to_name": settings.name, "file_name": filename},
		"file_url",
	)
	if existing:
		return existing
	return (
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
