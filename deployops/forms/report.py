"""PDF reports of submitted v2 forms (Plan 6): internal and customer copies.

Built from the form version the entry was filled on and its answers, so any form works. It reuses
the v1 report template and helpers (deployops.checklists.report): the same layout, embedded images
and job audit trail. Fields marked internal-only are left out of the customer copy, as is everything
that identifies the job internally.
"""

import base64
import io

import frappe
from forms_core import field_types, rules
from forms_core.submissions import _as_dict, _context_values, version_definition
from frappe import _
from frappe.utils import format_date, format_datetime, format_time, get_fullname

from deployops.checklists import report as v1

SUBMISSION = "Form Submission"
JOB = "DeployOps Job"
SIGNATURE_HEIGHT = 300


def check_reportable(doc, audience: str) -> None:
	if audience not in v1.AUDIENCES:
		frappe.throw(_("Unknown report audience {0}.").format(audience))
	if doc.docstatus != 1:
		frappe.throw(_("Only a submitted form has a report."))


def context(doc, audience: str = "internal") -> dict:
	check_reportable(doc, audience)
	internal = audience == "internal"
	definition = version_definition(doc.form_version)
	answers = _as_dict(doc.answers)
	form = frappe.db.get_value("Form", doc.form, ["title"], as_dict=True)
	version_no = frappe.db.get_value("Form Version", doc.form_version, "version_no")
	job = frappe.get_doc(JOB, doc.context_name) if doc.context_doctype == JOB and doc.context_name else None
	values = {}
	if job:
		from deployops.forms.provider import JobFormProvider

		values = _context_values(doc, JobFormProvider())
	submitted = format_datetime(doc.submitted_on, "d MMM yyyy, HH:mm") if doc.submitted_on else ""
	facts = [
		(_("Customer"), values.get("customer_name")),
		(_("Site"), values.get("address")),
		(_("Machine"), values.get("item_name") or values.get("item_code")),
		(_("Serial number"), values.get("serial_no")),
		(_("Technician"), values.get("technician")),
		(_("Submitted"), _("{0} by {1}").format(submitted, get_fullname(doc.submitted_by)) if doc.submitted_by else submitted),
	]
	if internal:
		facts += [(_("Entry"), doc.name), (_("Form version"), version_no)]
		if job:
			facts += [(_("Job"), job.name), (_("Source"), f"{_(job.source_doctype)} {job.source_name}"), (_("Company"), job.company)]
	sections = []
	for raw in definition.get("sections") or []:
		if not rules.evaluate(raw.get("show"), answers):
			continue
		blocks = _blocks(doc, raw.get("fields") or [], answers, internal)
		if blocks:
			sections.append({"label": raw.get("title"), "description": raw.get("description"), "blocks": blocks})
	return {
		"audience": audience,
		"title": form.title if form else doc.form,
		"name": doc.name,
		"logo": v1._data_url(v1.LOGO.read_bytes(), "image/png"),
		"facts": [(label, value) for label, value in facts if value not in (None, "")],
		"sections": sections,
		"audit": _audit(job, doc) if internal and job else [],
		"generated": format_datetime(frappe.utils.now_datetime(), "d MMM yyyy, HH:mm"),
	}


def render_html(doc, audience: str = "internal") -> str:
	return frappe.get_template(v1.TEMPLATE).render({"report": context(doc, audience)})


def render_pdf(doc, audience: str = "internal") -> bytes:
	from weasyprint import HTML

	return HTML(string=render_html(doc, audience), url_fetcher=v1.embedded_only_fetcher()).write_pdf()


# ---------------------------------------------------------------------------------------------


def _blocks(doc, fields: list[dict], answers: dict, internal: bool) -> list[dict]:
	blocks: list[dict] = []
	for field in fields:
		kind = field.get("type")
		if kind == "info" or not rules.evaluate(field.get("show"), answers):
			continue
		if field.get("internal_only") and not internal:
			continue
		value = answers.get(field.get("id"))
		label = field.get("label") or field.get("key")
		config = field.get("config") or {}
		if kind == "checkbox":
			if not blocks or blocks[-1]["kind"] != "steps":
				blocks.append({"kind": "steps", "steps": []})
			blocks[-1]["steps"].append({"label": label, "done": bool(value)})
		elif kind == "multi_check":
			chosen, other = _multi(value)
			steps = [{"label": option, "done": option in chosen} for option in config.get("options") or []]
			if other:
				steps.append({"label": _("Other: {0}").format(other), "done": True})
			done = len(chosen) + bool(other)
			blocks.append({"kind": "value", "label": label, "text": _("{0} of {1} ticked").format(done, len(steps)) if steps else ""})
			blocks.append({"kind": "steps", "steps": steps})
		elif kind == "table":
			columns = config.get("columns") or []
			rows = value or []
			blocks.append({
				"kind": "table",
				"label": label,
				"columns": [c.get("label") for c in columns],
				"rows": [[_text(c, (row or {}).get(c.get("id"))) for c in columns] for row in rows],
			})
		elif kind == "photos":
			blocks.append({"kind": "photos", "label": label, "photos": [
				{"src": v1._photo(_Attached(doc), item.get("file")), "caption": item.get("caption")}
				for item in value or [] if isinstance(item, dict) and item.get("file")
			]})
		elif kind == "files":
			blocks.append({"kind": "files", "label": label, "files": [
				(item.get("file") or "").rsplit("/", 1)[-1] for item in value or [] if isinstance(item, dict)
			]})
		elif kind == "signature":
			signed = value if isinstance(value, dict) else {}
			blocks.append({
				"kind": "signature",
				"label": label,
				"src": _signature(doc, signed.get("file")),
				"signer": signed.get("signer"),
				"signed_on": format_datetime(signed["signed_at"], "d MMM yyyy, HH:mm") if signed.get("signed_at") else "",
			})
		else:
			blocks.append({"kind": "value", "label": label, "text": _text(field, value)})
	return blocks


def _multi(value) -> tuple[set, str | None]:
	if isinstance(value, dict):  # {"selected": [...], "other": "..."}
		return set(value.get("selected") or value.get("values") or []), value.get("other")
	if isinstance(value, list):
		chosen, other = set(), None
		for item in value:
			if isinstance(item, dict):
				other = item.get("other") or other
			else:
				chosen.add(item)
		return chosen, other
	return set(), None


def _text(field: dict, value) -> str:
	if value in (None, "", []):
		return ""
	kind = field.get("type")
	try:
		if kind == "date":
			return format_date(value, "d MMM yyyy")
		if kind == "datetime":
			return format_datetime(value, "d MMM yyyy, HH:mm")
		if kind == "time":
			return format_time(value, "HH:mm")
		if kind == "multi_check":
			chosen, other = _multi(value)
			return ", ".join([*sorted(chosen), *([other] if other else [])])
		return field_types.get_type(kind).to_text(value, field)
	except Exception:
		return str(value)


class _Attached:
	"""What v1._photo needs to find a file attached to this entry."""

	def __init__(self, doc):
		self.doctype, self.name = SUBMISSION, doc.name


def _signature(doc, url: str | None) -> str | None:
	if not url:
		return None
	name = frappe.db.get_value("File", {"file_url": url, "attached_to_doctype": SUBMISSION, "attached_to_name": doc.name})
	if not name:
		return None
	try:
		from PIL import Image

		image = Image.open(io.BytesIO(frappe.get_doc("File", name).get_content(encodings=[])))
		image.thumbnail((SIGNATURE_HEIGHT * 4, SIGNATURE_HEIGHT))
		buffer = io.BytesIO()
		image.save(buffer, "PNG")
		return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
	except Exception:
		return None


def _audit(job, doc) -> list[dict]:
	row = next((r for r in job.devices if r.name == doc.context_row), None)
	machine = {f"{row.item_code} / {row.serial_no}", f"{row.item_code} (row {row.idx})"} if row else set()
	events = [
		(log.timestamp, log.user, log.action, f"{log.from_status} → {log.to_status}", log.reason)
		for log in job.status_log
		if not log.device or log.device in machine
	]
	events.append((doc.submitted_on or doc.modified, doc.submitted_by or doc.modified_by, _("form: submit"), doc.name, None))
	return [
		{"when": format_datetime(when, "d MMM yyyy, HH:mm"), "who": get_fullname(user), "action": action, "change": change, "reason": reason}
		for when, user, action, change, reason in sorted(events, key=lambda e: frappe.utils.get_datetime(e[0]))
	]
