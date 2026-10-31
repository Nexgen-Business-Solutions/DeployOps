# Checklist reports (#27)

A submitted checklist can be printed as a report or downloaded as a PDF. The **Cashmatic Pre-installation**, **Cashmatic Installation** and **Cashmatic Maintenance** checklists have one (`REPORTABLE` in `deployops/checklists/report.py`). The BellaBot checklists don't yet.

## What's in it
| Part | Internal report | Customer copy |
|---|---|---|
| Massarie logo, title | ✓ | ✓, marked "Customer copy" |
| Customer, site, machine, serial, technician, submitted on/by | ✓ | ✓ |
| Checklist, job, source document, company, form version | ✓ | — |
| Every section: ticked steps, values, tables (e.g. working hours), photos, signatures with signer and time | ✓ | ✓ |
| Audit trail: the job's status log for the job and this machine, plus the checklist submit (who, when, action, status, reason; no IP or device data) | ✓ | — |

The report is built from the checklist's **submission snapshot**, so it shows the questions and answers exactly as submitted, even if the form changes later. Nothing in it is specific to one checklist: sections, steps, values, tables, photos and signatures all come from the snapshot. That keeps it usable for the other checklists and for user-built forms later.

Drafts have no report.

## Where to get it
- **Technician app:** on a submitted checklist, **Report (PDF)** and **Customer copy (PDF)** under the "Submitted" banner.
- **Desk:** open the checklist, **Print**, then pick the checklist's report: **Cashmatic Pre-installation Report** or **Cashmatic Installation Report**, each with a **(Customer)** version. Print from the browser to save as PDF. Cashmatic Maintenance has no Desk print formats yet; use the app or the API.
- **API:** `GET /api/method/deployops.api.reports.checklist_pdf?doctype=…&name=…&audience=internal|customer`.

## Security
- The same access as printing the form, which follows job visibility: the assigned technician, and Supervisors and Managers whose equipment covers the machine. Other users and guests are refused (403).
- Each PDF download is written to the **Access Log** (method `Report: internal` or `Report: customer`).
- Photos, signatures and the logo are **embedded** in the report. It never links to a private file, and the PDF renderer refuses to fetch anything else.
- Photos are read only from files attached to that checklist, and are resized to 1200 px.
- Stored text is shown as plain text and escaped, so text typed into a checklist can't add markup to the report.

## Admin notes
- **PDF engine:** WeasyPrint, which ships with Frappe v16; no wkhtmltopdf or Chrome needed.
- **Logo:** `deployops/public/images/massarie-logo.png` (from the Massarie Jotform). Replace the file to change it.
- **Layout:** `deployops/templates/checklist_report.html`. Both Desk print formats call the same template through the Jinja method `checklist_report_html(doc, audience)`.
- **Another checklist:** add its DocType to `REPORTABLE` and give it two Print Formats like the pre-installation ones (`deployops/deployops/print_format/`).

## Tests
`deployops/tests/test_reports.py` covers:
- the report is built from the snapshot, not current values;
- every step appears, and the evidence is embedded;
- what the customer copy leaves out;
- the order of the audit trail;
- escaping;
- drafts are refused;
- a real PDF is produced;
- the Desk formats render;
- who may download, and that downloads are logged;
- the app offers the links once submitted;
- guests are refused over HTTP.
