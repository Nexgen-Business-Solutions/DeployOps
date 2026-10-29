"""Printable checklist reports (#27): a submitted checklist as an HTML page or a PDF.

The report is built from the form's submission snapshot, so it shows the exact questions that were
answered, and it does not depend on any one form: every section, step, value, table, photo and
signature comes from the snapshot. Two audiences:

- ``internal``: everything, with the job reference, form version and the job's audit trail;
- ``customer``: the same answers and evidence without internal references or the audit trail.

Photos, signatures and the logo are embedded as data URLs, so a report never links to a private file
and the PDF renderer never fetches anything.
"""

import base64
import html
import io
import re
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import format_date, format_datetime, format_time, get_datetime, get_fullname, strip_html

from deployops.checklists.cards import CARDS
from deployops.checklists.form import SIGNATURE_PREFIX

AUDIENCES = ("internal", "customer")
TEMPLATE = "deployops/templates/checklist_report.html"
LOGO = Path(__file__).parent.parent / "public" / "images" / "massarie-logo.png"
PHOTO_SIZE = 1200  # longest side in the report, in pixels

# Checklists with confirmed PDF reports. The renderer works for any checklist with a
# submission snapshot; add a doctype here once its report layout is product-owner approved.
REPORTABLE = (
	"DeployOps Cashmatic Pre-installation",
	"DeployOps Cashmatic Maintenance",
)


def check_reportable(doc, audience: str):
	if doc.doctype not in REPORTABLE:
		frappe.throw(_("{0} has no report yet.").format(_(doc.doctype)))
	if audience not in AUDIENCES:
		frappe.throw(_("Unknown report audience {0}.").format(audience))
	if doc.docstatus != 1 or not doc.submission_snapshot:
		frappe.throw(_("Only a submitted checklist has a report."))


def context(doc, audience: str = "internal") -> dict:
	"""Everything the template needs, already formatted; values are escaped by the template."""
	check_reportable(doc, audience)
	snapshot = frappe.parse_json(doc.submission_snapshot)
	values = snapshot["values"]
	signatures = snapshot.get("signatures") or {}
	internal = audience == "internal"
	job = frappe.get_doc("DeployOps Job", doc.job)
	title = next((card["title"] for card in CARDS if card["doctype"] == doc.doctype), _(doc.doctype))
	submitted = format_datetime(doc.modified, "d MMM yyyy, HH:mm")

	facts = [
		(_("Customer"), doc.customer_name),
		(_("Site"), _plain(doc.site_address)),
		(_("Machine"), doc.item_name or doc.item_code),
		(_("Serial number"), doc.serial_no),
		(_("Technician"), get_fullname(doc.technician) if doc.technician else None),
		(_("Submitted"), _("{0} by {1}").format(submitted, get_fullname(doc.modified_by))),
	]
	if internal:
		facts += [
			(_("Checklist"), doc.name),
			(_("Job"), job.name),
			(_("Source"), f"{_(job.source_doctype)} {job.source_name}"),
			(_("Company"), doc.company),
			(_("Form version"), snapshot.get("form_version")),
		]

	return {
		"audience": audience,
		"title": title,
		"name": doc.name,
		"logo": _data_url(LOGO.read_bytes(), "image/png"),
		"facts": [(label, value) for label, value in facts if value not in (None, "")],
		"sections": [
			section
			for section in (
				_section(doc, raw, values, signatures)
				for raw in snapshot["sections"]
				if _shown(raw.get("show"), values)
			)
			if section["blocks"]
		],
		"audit": _audit(job, doc) if internal else [],
		"generated": format_datetime(frappe.utils.now_datetime(), "d MMM yyyy, HH:mm"),
	}


def render_html(doc, audience: str = "internal") -> str:
	return frappe.get_template(TEMPLATE).render({"report": context(doc, audience)})  # a fixed app file


def embedded_only_fetcher():
	"""A WeasyPrint URL fetcher that loads only data URLs: images are embedded, nothing else is fetched.

	Built on `URLFetcher` (WeasyPrint 68+); version 70 removed `default_url_fetcher`.
	"""
	from weasyprint.urls import URLFetcher

	class EmbeddedOnly(URLFetcher):
		def fetch(self, url, headers=None):
			if not url.startswith("data:"):
				raise ValueError(f"Reports do not load external resources: {url}")
			return super().fetch(url, headers)

	return EmbeddedOnly()


def render_pdf(doc, audience: str = "internal") -> bytes:
	from weasyprint import HTML

	return HTML(string=render_html(doc, audience), url_fetcher=embedded_only_fetcher()).write_pdf()


def checklist_report_html(doc, audience: str = "internal") -> str:
	"""Jinja method for the Desk print formats."""
	return render_html(doc, audience)


# ---------------------------------------------------------------------------------------------


def _shown(condition: dict | None, values: dict) -> bool:
	return not condition or values.get(condition["field"]) == condition["value"]


def _section(doc, raw: dict, values: dict, signatures: dict) -> dict:
	"""A section as blocks: consecutive ticks become one step list, the rest one block per field."""
	blocks: list[dict] = []
	for field in raw["fields"]:
		if not _shown(field.get("show"), values) or field["fieldtype"] == "HTML":
			continue
		value = values.get(field["fieldname"])
		if field["fieldtype"] == "Check":
			if not blocks or blocks[-1]["kind"] != "steps":
				blocks.append({"kind": "steps", "steps": []})
			blocks[-1]["steps"].append({"label": field["label"], "done": bool(value)})
		elif field["fieldtype"] == "Table":
			blocks.append(_table(doc, field, value or []))
		elif field["fieldtype"] == "Signature":
			signed = signatures.get(field["fieldname"]) or {}
			blocks.append(
				{
					"kind": "signature",
					"label": field["label"],
					"src": value if isinstance(value, str) and value.startswith(SIGNATURE_PREFIX) else None,
					"signer": signed.get("signer_name"),
					"signed_on": _format("Datetime", signed.get("signed_on")),
				}
			)
		else:
			blocks.append(
				{"kind": "value", "label": field["label"], "text": _format(field["fieldtype"], value)}
			)
	return {"label": raw.get("label"), "description": raw.get("description"), "blocks": blocks}


def _table(doc, field: dict, rows: list[dict]) -> dict:
	table = field["table"]
	label = field["label"]
	if table["kind"] in ("photos", "files"):
		column = table["file_column"]
		caption = next((c["fieldname"] for c in table["columns"] if c["fieldname"] != column), None)
		items = [
			{"url": row.get(column), "caption": row.get(caption) if caption else None}
			for row in rows
			if row.get(column)
		]
		if table["kind"] == "photos":
			return {
				"kind": "photos",
				"label": label,
				"photos": [{"src": _photo(doc, item["url"]), "caption": item["caption"]} for item in items],
			}
		return {"kind": "files", "label": label, "files": [item["url"].rsplit("/", 1)[-1] for item in items]}
	columns = table["columns"]
	return {
		"kind": "table",
		"label": label,
		"columns": [c["label"] for c in columns],
		"rows": [[_format(c["fieldtype"], row.get(c["fieldname"])) for c in columns] for row in rows],
	}


def _format(fieldtype: str, value) -> str:
	if value in (None, ""):
		return ""
	if fieldtype == "Check":
		return _("Yes") if value else _("No")
	if fieldtype == "Datetime":
		return format_datetime(value, "d MMM yyyy, HH:mm")
	if fieldtype == "Date":
		return format_date(value, "d MMM yyyy")
	if fieldtype == "Time":
		return format_time(value, "HH:mm")
	# Frappe stores text sanitised as HTML (& becomes &amp;); the report shows it as plain text.
	return html.unescape(strip_html(str(value)))


def _photo(doc, url: str) -> str | None:
	"""The photo as a data URL, read only from a file attached to this form (as validation requires)."""
	name = frappe.db.get_value(
		"File", {"file_url": url, "attached_to_doctype": doc.doctype, "attached_to_name": doc.name}
	)
	if not name:
		return None
	try:
		# No encodings: the raw bytes (by default it returns text whenever the bytes happen to decode).
		content = frappe.get_doc("File", name).get_content(encodings=[])
		from PIL import Image, ImageOps

		image = ImageOps.exif_transpose(Image.open(io.BytesIO(content)))
		image.thumbnail((PHOTO_SIZE, PHOTO_SIZE))
		buffer = io.BytesIO()
		image.convert("RGB").save(buffer, "JPEG", quality=80)
		return _data_url(buffer.getvalue(), "image/jpeg")
	except Exception:
		return None  # not a readable image: the report lists it without a picture


def _audit(job, doc) -> list[dict]:
	"""The job's status log for the job and this machine: who did what, when (no IP or device data)."""
	row = next((r for r in job.devices if r.name == doc.job_device), None)
	machine = {f"{row.item_code} / {row.serial_no}", f"{row.item_code} (row {row.idx})"} if row else set()
	events = [
		(log.timestamp, log.user, log.action, f"{log.from_status} → {log.to_status}", log.reason)
		for log in job.status_log
		if not log.device or log.device in machine
	]
	events.append((doc.modified, doc.modified_by, _("checklist: submit"), doc.name, None))
	return [
		{
			"when": format_datetime(when, "d MMM yyyy, HH:mm"),
			"who": get_fullname(user),
			"action": action,
			"change": change,
			"reason": reason,
		}
		for when, user, action, change, reason in sorted(events, key=lambda event: get_datetime(event[0]))
	]


def _plain(html: str | None) -> str | None:
	"""ERPNext's address display is HTML; the report shows it as plain lines."""
	if not html:
		return html
	lines = strip_html(re.sub(r"<br\s*/?>", "\n", html)).splitlines()
	return "\n".join(line.strip() for line in lines if line.strip())


def _data_url(content: bytes, mime: str) -> str:
	return f"data:{mime};base64,{base64.b64encode(content).decode()}"
