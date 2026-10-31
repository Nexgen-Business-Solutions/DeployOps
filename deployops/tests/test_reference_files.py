"""Reference files (#42): manuals shown to technicians inside the checklists, kept private."""

import io
import tempfile
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests.classes.context_managers import set_user

from deployops import install
from deployops.api import technician as api
from deployops.roles import ADMINISTRATOR
from deployops.tests.test_checklists import ChecklistTestCase
from deployops.tests.utils import make_role_user

SETTINGS = "DeployOps Reference Files"
PRE_INSTALLATION = "DeployOps Cashmatic Pre-installation"
SECTION = "machine_activation_steps_section"


def blank_pdf() -> bytes:
	"""A real, unique one-page PDF: Frappe checks uploaded PDFs and de-duplicates equal files."""
	from pypdf import PdfWriter

	writer, buffer = PdfWriter(), io.BytesIO()
	writer.add_blank_page(72, 72)
	writer.add_metadata({"/Title": frappe.generate_hash()})
	writer.write(buffer)
	return buffer.getvalue()


class ReferenceTestCase(ChecklistTestCase):
	def setUp(self):
		super().setUp()
		self.admin = make_role_user(ADMINISTRATOR)

	def upload(self, name="cdig.pdf", private=1, attached_to=SETTINGS):
		return (
			frappe.get_doc(
				{
					"doctype": "File",
					"file_name": name,
					"content": blank_pdf() if name.endswith(".pdf") else frappe.generate_hash().encode(),
					"is_private": private,
					"attached_to_doctype": attached_to,
					"attached_to_name": attached_to,
				}
			)
			.insert(ignore_permissions=True)
			.file_url
		)

	def set_references(self, rows):
		settings = frappe.get_single(SETTINGS)
		settings.set("references", rows)
		settings.save(ignore_permissions=True)
		return settings

	def row(self, file, checklist=PRE_INSTALLATION, section=SECTION, title="CDIG"):
		return {"title": title, "file": file, "checklist": checklist, "section": section}


class TestReferenceSettings(ReferenceTestCase):
	def test_only_private_files_of_these_settings_in_a_real_section(self):
		good = self.upload()
		self.set_references([self.row(good), self.row(good, section=None, title="CDIG (top)")])
		cases = {
			"public file": self.row(self.upload("public.pdf", private=0)),
			"file of another document": self.row(self.upload("other.pdf", attached_to="DeployOps Job")),
			"not a PDF or image": self.row(self.upload("notes.txt")),
			"unknown section": self.row(good, section="no_such_section"),
			"a field, not a section": self.row(good, section="software_version"),
		}
		for case, row in cases.items():
			with self.subTest(case=case), self.assertRaises(frappe.ValidationError):
				self.set_references([row])

	def test_only_the_administrator_maintains_them(self):
		for user in (self.technician, self.supervisor, self.manager):
			with self.subTest(user=user), set_user(user):
				self.assertTrue(frappe.has_permission(SETTINGS, "read"))
				self.assertFalse(frappe.has_permission(SETTINGS, "write"))
		with set_user(self.admin):
			self.assertTrue(frappe.has_permission(SETTINGS, "write"))


class TestReferencesInTheChecklist(ReferenceTestCase):
	def test_the_form_lists_its_references_by_section(self):
		cdig, manual = self.upload(), self.upload("manual.pdf")
		self.set_references(
			[
				self.row(cdig),
				self.row(manual, section=None, title="User manual"),
				self.row(
					cdig, checklist="DeployOps Cashmatic Installation", section=None, title="Other checklist"
				),
			]
		)
		name = self.start(self.working_job("Pre-installation"))
		with set_user(self.technician):
			view = api.form_view(PRE_INSTALLATION, name)
		self.assertEqual(
			view["references"],
			[
				{"title": "CDIG", "url": cdig, "section": SECTION},
				{"title": "User manual", "url": manual, "section": None},
			],
		)
		self.assertIn(SECTION, [s["name"] for s in view["sections"]])

	def test_the_files_open_only_for_deployops_users(self):
		url = self.upload()
		self.set_references([self.row(url)])
		file = frappe.get_doc("File", {"file_url": url})
		outsider = "_ref-outsider@deployops.test"
		frappe.get_doc(
			{"doctype": "User", "email": outsider, "first_name": "Out", "send_welcome_email": 0}
		).insert(ignore_permissions=True)
		for user, allowed in (
			(self.technician, True),
			(self.supervisor, True),
			(outsider, False),
			("Guest", False),
		):
			with self.subTest(user=user):
				self.assertEqual(bool(frappe.has_permission("File", "read", file, user=user)), allowed)


class TestBundledReferences(ReferenceTestCase):
	def test_install_seeds_bundled_files_once_and_skips_missing_ones(self):
		self.set_references([])
		with tempfile.TemporaryDirectory() as folder:
			(Path(folder) / "device-installation-guide.pdf").write_bytes(blank_pdf())
			with patch.object(install.frappe, "get_app_path", return_value=folder):
				install.install_reference_files()
				settings = frappe.get_single(SETTINGS)
				self.assertEqual(
					[(r.checklist, r.section) for r in settings.references],
					[
						(PRE_INSTALLATION, "machine_configuration_steps_section"),
						(PRE_INSTALLATION, "machine_activation_steps_section"),
						(install.INSTALLATION, "machine_positioning_evaluation_section"),
						(install.INSTALLATION, "power_and_network_section"),
					],
				)
				self.assertEqual(len({r.file for r in settings.references}), 1)  # one upload, four places
				install.install_reference_files()  # the administrator's list is never overwritten
				self.assertEqual(len(frappe.get_single(SETTINGS).references), 4)
