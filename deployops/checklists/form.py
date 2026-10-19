"""Shared behaviour of the five checklist DocTypes (#20/#41): one form per machine on a job.

Each form is a native DocType whose fields come from its source Jotform. Drafts save with gaps
(autosave); everything required is checked on submit. Each controller only declares its extra rules:

- ``ANY_OF``: section → Check fields, at least one visible box must be ticked;
- ``MIN_ROWS``: table → minimum rows (e.g. three installation photos);
- ``FIXED_ROWS``: table → (column, labels), rows created with the form and never changed;
- ``FORM_VERSION``: bump it whenever the DocType's questions change (see CHECKLIST_ARCHITECTURE.md);
- ``SIGNERS``: Signature field → the field holding the signer's name ("technician" = the job's technician).

Each form records the version it was started on, and on submit keeps a snapshot of every question
and answer, so a submitted checklist always shows what was actually asked.

A Check with ``reqd`` must be ticked. ``depends_on`` / ``mandatory_depends_on`` only support the
form ``eval:doc.<field>=='<value>'``, so the server and the app read them the same way.
"""

import re
from typing import ClassVar

import frappe
from frappe import _
from frappe.model import no_value_fields
from frappe.model.document import Document
from frappe.utils import now_datetime

from deployops.checklists.cards import card_for, form_for_device
from deployops.workflow import job_workflow

JOB = "DeployOps Job"
# Filled by the server only: who signed each signature and when (#21).
SIGNATURES = "signatures"
HEADER_FIELDS = (
	"job",
	"job_device",
	"customer_name",
	"site_address",
	"item_code",
	"item_name",
	"serial_no",
	"technician",
	"company",
	"form_version",
	"submission_snapshot",
)
TEXT_TYPES = ("Data", "Small Text", "Text", "Long Text")
FILE_COLUMNS = {"DeployOps Checklist Photo": "image", "DeployOps Checklist File": "file"}
HOURS = "DeployOps Checklist Opening Hours"
CONDITION = re.compile(r"^eval:doc\.(\w+)\s*==\s*'([^']*)'$")
SIGNATURE_PREFIX = "data:image/png;base64,"
MAX_SIGNATURE = 400_000
SECRET_PATTERN = re.compile(
	r"\b(password|passwd|pwd|mot de passe|otp|pin|pairing code|code d'appairage)\b\s*[:=]\s*\S",
	re.IGNORECASE,
)


def looks_like_secret(value) -> bool:
	return bool(value) and isinstance(value, str) and bool(SECRET_PATTERN.search(value))


def condition_met(doc, expression: str | None) -> bool:
	if not expression:
		return True
	match = CONDITION.match(expression.strip())
	if not match:
		frappe.throw(_("Unsupported condition {0} on {1}.").format(expression, doc.doctype))
	return (doc.get(match[1]) or "") == match[2]


def is_empty(value) -> bool:
	return value is None or (isinstance(value, str) and not value.strip())


class ChecklistForm(Document):
	ANY_OF: ClassVar[dict[str, list[str]]] = {}
	MIN_ROWS: ClassVar[dict[str, int]] = {}
	FIXED_ROWS: ClassVar[dict[str, tuple[str, tuple[str, ...]]]] = {}
	FORM_VERSION = 1
	SIGNERS: ClassVar[dict[str, str]] = {}
	INTRO = ""

	def before_insert(self):
		job = frappe.get_doc(JOB, self.job)
		device = self.get_device(job)
		if job.status not in job_workflow.WORKING:
			frappe.throw(_("A checklist can only be started while the job is being worked on."))
		if device.device_status == "Cancelled":
			frappe.throw(_("This machine was cancelled on the job."))
		card = card_for(job.job_type, device.item_code)
		if not card or card["doctype"] != self.doctype:
			frappe.throw(
				_("{0} is not the checklist for this machine on a {1} job.").format(
					_(self.doctype), _(job.job_type)
				)
			)
		if form_for_device(job.name, device.name):
			frappe.throw(_("This machine already has a checklist on this job."))

		self.update(
			{
				"customer_name": job.customer_name,
				"site_address": job.address_display,
				"item_code": device.item_code,
				"item_name": device.item_name,
				"serial_no": device.serial_no,
				"technician": job.assigned_technician,
				"company": job.company,
				"form_version": self.FORM_VERSION,
			}
		)
		# Fields such as "Device" that show the machine's own Item data (fetch_from item_code.*).
		for df in self.meta.fields:
			if (df.fetch_from or "").startswith("item_code."):
				self.set(
					df.fieldname,
					frappe.db.get_value("Item", device.item_code, df.fetch_from.split(".", 1)[1]),
				)
		for field, (column, labels) in self.FIXED_ROWS.items():
			self.set(field, [{column: label} for label in labels])

	def get_device(self, job):
		device = next((row for row in job.devices if row.name == self.job_device), None)
		if not device:
			frappe.throw(_("That machine is not on job {0}.").format(job.name))
		return device

	def validate(self):
		if self.docstatus == 0:
			self.flags.ignore_mandatory = True  # drafts save with gaps; before_submit checks them
		self.validate_header()
		self.validate_fixed_rows()
		self.validate_values()
		self.record_signatures()

	def validate_header(self):
		before = self.get_doc_before_save()
		if not before:
			return
		for field in HEADER_FIELDS:
			if self.get(field) != before.get(field):
				frappe.throw(
					_("{0} comes from the job and cannot be changed.").format(_(self.meta.get_label(field)))
				)

	def validate_fixed_rows(self):
		for field, (column, labels) in self.FIXED_ROWS.items():
			if [row.get(column) for row in self.get(field)] != list(labels):
				frappe.throw(
					_("{0}: the rows are fixed and cannot be added, removed or renamed.").format(
						_(self.meta.get_label(field))
					)
				)

	def validate_values(self):
		for df in self.meta.fields:
			value = self.get(df.fieldname)
			if df.fieldtype in TEXT_TYPES and looks_like_secret(value):
				self.refuse_secret(df.label)
			elif df.fieldtype == "Signature" and value:
				if not value.startswith(SIGNATURE_PREFIX) or len(value) > MAX_SIGNATURE:
					frappe.throw(_("{0}: the signature is not a valid image.").format(_(df.label)))
			elif df.fieldtype == "Table":
				for row in value or []:
					self.validate_row(df, row)

	def validate_row(self, df, row):
		for child in frappe.get_meta(df.options).fields:
			if child.fieldtype in TEXT_TYPES and looks_like_secret(row.get(child.fieldname)):
				self.refuse_secret(df.label)
		column = FILE_COLUMNS.get(df.options)
		url = row.get(column) if column else None
		if url and (
			self.is_new()
			or not frappe.db.exists(
				"File",
				{
					"file_url": url,
					"is_private": 1,
					"attached_to_doctype": self.doctype,
					"attached_to_name": self.name,
				},
			)
		):
			frappe.throw(_("{0}: upload the file to this checklist first.").format(_(df.label)))

	def signer_name(self, fieldname: str) -> str | None:
		source = self.SIGNERS.get(fieldname)
		if source == "technician":
			return frappe.db.get_value("User", self.technician, "full_name") if self.technician else None
		return self.get(source) if source else None

	def record_signatures(self):
		"""Rebuild the signature record from the form: signer name, and when and by whom each
		signature was captured. Times are kept from the saved record until the drawing changes."""
		before = self.get_doc_before_save()
		saved = {row.signature_field: row for row in (before.get(SIGNATURES) if before else [])}
		rows = []
		for df in self.meta.fields:
			if df.fieldtype != "Signature" or not self.get(df.fieldname):
				continue
			old = saved.get(df.fieldname)
			unchanged = old and before and before.get(df.fieldname) == self.get(df.fieldname)
			rows.append(
				{
					"signature_field": df.fieldname,
					"signature_label": df.label,
					"signer_name": self.signer_name(df.fieldname),
					"signed_on": old.signed_on if unchanged else now_datetime(),
					"captured_by": old.captured_by if unchanged else frappe.session.user,
				}
			)
		self.set(SIGNATURES, rows)

	def refuse_secret(self, label):
		frappe.throw(
			_("{0}: do not enter passwords, PINs, OTPs or pairing codes in a checklist.").format(_(label))
		)

	def before_submit(self):
		problems = self.missing()
		if problems:
			frappe.throw(
				_("The checklist is not complete:") + "<br>" + "<br>".join(problems),
				title=_("Missing answers"),
			)
		if self.form_version != self.FORM_VERSION:
			frappe.throw(
				_(
					"This checklist was started on form version {0}; the form is now version {1}. Ask a manager to cancel it and start a new one."
				).format(self.form_version, self.FORM_VERSION)
			)
		self.submission_snapshot = self.snapshot()

	def snapshot(self) -> str:
		from deployops.checklists import layout  # layout imports this module

		return frappe.as_json(
			{
				"form_version": self.form_version,
				"sections": layout.sections(self),
				"values": layout.values(self),
				"signatures": layout.signatures(self),
			},
			indent=None,
		)

	def is_visible(self, df) -> bool:
		return not df.hidden and condition_met(self, df.depends_on)

	def missing(self) -> list[str]:
		"""Every reason the form cannot be submitted yet, in form order."""
		problems = []
		any_of_fields = {field for fields in self.ANY_OF.values() for field in fields}
		for df in self.meta.fields:
			if df.fieldname in HEADER_FIELDS or df.fieldname == SIGNATURES or not self.is_visible(df):
				continue
			label = _(df.label)
			if df.fieldtype == "Signature" and self.get(df.fieldname) and not self.signer_name(df.fieldname):
				problems.append(_("{0}: the signer's name is required.").format(label))
			if df.fieldtype == "Section Break" and df.fieldname in self.ANY_OF:
				boxes = [self.meta.get_field(name) for name in self.ANY_OF[df.fieldname]]
				visible = [box for box in boxes if self.is_visible(box)]
				if visible and not any(self.get(box.fieldname) for box in visible):
					problems.append(_("{0}: tick at least one.").format(label))
				continue
			if df.fieldtype in no_value_fields and df.fieldtype != "Table":
				continue
			required = df.reqd or (df.mandatory_depends_on and condition_met(self, df.mandatory_depends_on))
			if df.fieldtype == "Check":
				if required and df.fieldname not in any_of_fields and not self.get(df.fieldname):
					problems.append(_("{0}: not ticked.").format(label))
			elif df.fieldtype == "Table":
				problems.extend(self.missing_rows(df, required))
			elif required and is_empty(self.get(df.fieldname)):
				problems.append(_("{0}: required.").format(label))
		return problems

	def missing_rows(self, df, required) -> list[str]:
		rows = self.get(df.fieldname) or []
		label = _(df.label)
		minimum = self.MIN_ROWS.get(df.fieldname) or (1 if required else 0)
		if len(rows) < minimum:
			return [_("{0}: at least {1} needed.").format(label, minimum)]
		problems = []
		columns = [c for c in frappe.get_meta(df.options).fields if c.reqd and not c.read_only]
		for row in rows:
			name = row.get(self.FIXED_ROWS[df.fieldname][0]) if df.fieldname in self.FIXED_ROWS else row.idx
			if df.options == HOURS:
				if not row.closed and not (row.open_time and row.close_time):
					problems.append(
						_("{0}, {1}: opening and closing time, or Closed.").format(label, _(name))
					)
				continue
			for column in columns:
				if is_empty(row.get(column.fieldname)):
					problems.append(_("{0}, {1}: {2} required.").format(label, _(name), _(column.label)))
		return problems
