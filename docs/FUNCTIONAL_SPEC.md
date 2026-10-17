# DeployOps — Functional Specification

**Status:** Requirements baseline from product-owner discussions; detailed form mapping and several transitions remain **pending sign-off**. Do not treat proposals as approved software behavior.

## 1. Business objective
Centralize technical pre-installation, on-site commissioning/installation and maintenance inside Massarie's ERPNext site for multiple equipment families. All checklist forms must be **native Frappe**, not embedded Jotform. A technician operates from verified ERPNext customer, product, service and serial data instead of retyping information.

## 2. Scope for V1
- Five checklists: Cashmatic pre-installation (#22), Cashmatic on-site (#23), BellaBot Pro pre-installation (#24), BellaBot Pro on-site (#25), Cashmatic maintenance (#26).
- Operational jobs, assignments, scheduling, readiness decisions, approval exceptions and traceability.
- Equipment-aware authorization separate from generic user roles.
- Links to ERPNext sales, delivery, subscriptions and maintenance documents.
- Signed/photo evidence, printable reports and audit trail.
Out of scope until separately approved: reimplementing CRM, billing, stock ledger, accounting, generic rental billing engine, asset capitalization, or manufacturer-specific roles.

## 3. Core actors and rules
| Actor | Intended authority |
|---|---|
| Technician | execute assigned jobs/checklists on authorized equipment |
| Supervisor | review/reassign/approve within scope |
| Manager | oversee authorized operational domain; scheduling and exceptions |
| Administrator | manage templates, categories, access settings and authorized system configuration |
Permissions are **not** granted automatically based on a supplier name. Effective access requires role + product/category profile + job-level authorization, enforced in backend.

## 4. Business journeys
### 4.1 Equipment sold
- Submitted Sales Order establishes confirmed item/customer context. Whether payment or invoice must exist before preparation is **to be decided**.
- Pre-installation should use customer/contact/site and ordered Items. Physical serial can be assigned during pre-installation when device configuration/activation is required.
- On-site installation references the actual Delivery Note and serialized Item/Serial No. A Delivery Note may contain multiple machines; track each independently and prevent serial mismatch.
- Technician records checklist and evidence, customer acceptance and manager approval if required. Preserve history and related documents.

### 4.2 Rented equipment
- Existing ERPNext **Subscription** manages recurring rental fees.
- DeployOps links that billing context to the **specific serial-numbered physical equipment** allocated to customer. If service Item and physical Item differ, explicitly map them.
- Preserve reserved/deployed/returned/swapped history and availability safeguards. No assumption that a service invoice or Subscription performs warehouse movement.
- Installations require the same quality/checklist controls; may use a Delivery Note if one exists or a controlled alternative deployment record.

### 4.3 Maintenance
- Initiated/linked through ERPNext Maintenance Visit and existing Maintenance Schedule; preserve maintenance coverage reference when available.
- Technician completes component-level checklist, remarks and sign-off, linked to customer and physical serial.
- Maintenance completion and visit completion must be reconciled; do not create a second independent maintenance history.

## 5. Data provenance
Prepopulate and retain source document links, customer, Contact, Address/site, Item, assigned serial, technician, visit date, commercial/rental reference. Confirm important site/contact changes through controlled update, not silent overwriting of ERPNext masters. Use read-only snapshots of identifying data at submission, while retaining original links.

## 6. Workflow (design proposal)
| Stage | Meaning | Gate |
|---|---|---|
| Draft | initial job or checklist | valid source |
| In Preparation | customer readiness and device configuration | role/profile/assignment |
| Blocked | missing requirement, NO GO or safety exception | reason and remediation |
| Ready for Deployment | prerequisites accepted | required checklist complete and valid serial when applicable |
| On Site | field installation/commissioning | valid delivery/deployment link |
| Pending Review | evidence/signature completed | reviewer if configured |
| Completed | accepted result | all applicable device outcomes approved |
| Returned for Correction | reviewer rejects | reason, history |
Final states/transition rights, overrides, supervisor sign-off policy and scheduling triggers are not yet owner-approved (#19).

## 7. Validation and evidence
- Field input must be typed and validated on server, including serial-to-Item, customer, company, source-document state and equipment allocation conflicts.
- Status options for checklist steps may include Pending, Completed, Not Applicable and Blocked; policy for evidence/NA justification pending confirmation.
- Support photos, technical remarks, document attachments and employee/customer signatures as required by individual source forms.
- Signed reports preserve author, signature evidence, date/time, source links and checklist revision; permissioned export.
- Never store passwords, OTPs, pairing credentials or other secrets in comments, PDFs or photos of credentials.

## 8. UAT acceptance scenarios
1. Sold single Cashmatic: Sales Order -> pre-install serial/config -> Delivery Note -> on-site signed report.
2. Two machines in same Delivery Note: independent serial and completion statuses.
3. Wrong/nonmatching serial or already allocated serial rejected.
4. Rental Subscription creates billing reference, but a specific robot serial is separately allocated, returned, swapped.
5. BellaBot pre-install NO GO blocks deployment; GO WITH CONDITIONS requires documented resolution/approval rule.
6. Maintenance Visit -> component checklist -> traceable signed result.
7. User without equipment profile or assigned job cannot list, open, update, print, export or access photos via direct endpoint.
8. Existing trial Cashmatic Installation records untouched until audited/approved for retirement.
9. Completed forms remain reproducible against same checklist version.

## 9. Items requiring owner confirmation before relevant features begin
- Which confirmation/payment threshold authorizes new jobs.
- When serial becomes compulsory for each checklist and which stock/inventory conditions permit assignment.
- Who can override blocked or NO GO; whether approval always or only on exceptions.
- Customer signature requirements, remote sign-off and employee signatures per form.
- Exact Jotform conditional logic, field options and mandatory settings not recoverable solely from completed PDFs.
- Desired rental return inventory process, Subscription-to-physical-Item mapping, device replacement process.
- Working-hours storage approach, final report design and offline/mobile access.

## 10. Issue mapping
#8-#9 technical foundation; #10-#12 permissions; #13-#17 integrations; #18-#19 workflows; #20-#21 native forms; #22-#26 checklist migration; #27 reports; #30 UAT; #31 retirement; #32 release.
