# DeployOps — Checklist Migration Specifications

**Status:** SOURCE INVENTORY / PARTIAL FIELD MAPPING. **Not yet approved as exhaustive implementation specification.** The five Jotforms are the original references; a completed **Pre-Visit-Installation Checklist – Grillades Amira LaSalle** PDF (September 23, 2026, five pages including audit trail) was supplied for the first form. This source includes live customer/employee details and credentials and **must not be committed to the repository**. Reproduce technical requirements, not sample passwords, personal contacts, or sensitive evidence.

## Sources
| Form | Original URL | Backlog |
|---|---|---|
| Cashmatic Pre-installation | https://form.jotform.com/253063954693264 | #22 |
| BellaBot Pro Pre-installation | https://form.jotform.com/262743846222055 | #24 |
| Cashmatic On-site Installation | https://form.jotform.com/253064644317254 | #23 |
| BellaBot Pro On-site Installation | https://form.jotform.com/262743396548066 | #25 |
| Cashmatic Maintenance | https://form.jotform.com/253383306590256 | #26 |

## Migration rules for all
1. Native Frappe inputs, not iframe/Jotform embedding.
2. Identify original label, section, type, choices, instructions, visibility rules, mandatory criteria and validation for **each** field; preserve field-level technical instructions.
3. Mark requirements as **Observed in completed PDF**, **Observed in original form**, **ERPNext-derived**, or **Proposed**. Missing builder-only logic goes into an open-questions register.
4. ERPNext-sourced customer, Item, Serial No, Contact, address, Delivery Note, Sales Order, Subscription or Maintenance Visit are linked, permission checked and only editable where specifically allowed.
5. Capture explicit technician action, evidence, exceptions, signature and final outcome. Protect secrets and sensitive data.
6. Complete typed field mapping table and obtain product-owner sign-off before coding each checklist; this document is intentionally **not** a claim that every original Jotform field/condition is verified.

## 1. Cashmatic Pre-installation — detailed PDF-derived inventory
**Source:** Completed pre-visit PDF, pages 1-5. Document says to complete checklist **one week before installation**. Device example Self Pay 460; activation and software/firmware information was recorded before installation. The PDF displays checklist text, sample fields and audit trail, but **not** definitive builder-only mandatory/conditional rules.

### A. Shared documents before visit (PDF p.1)
| Original action | Frappe proposal |
|---|---|
| Forward User Manual to technician; ensure review | confirmation, technician and date |
| Send Self Pay 460 User Manual to client | confirmation |
| Send Web panel interface to client | confirmation |
| Send explanation of My Cashmatic App to client | confirmation |
**Design note:** Reference documentation needs versioned central links. Proof that client received materials is a policy question.

### B. Employee readiness and physical preparation (p.1)
| Original action | Frappe proposal |
|---|---|
| Apply company logo and QR code on machine | checklist + optional evidence |
| Confirm with client machine installation area is clear and clean | customer-confirmed readiness |
| Confirm available electrical plug | customer-confirmed readiness |
| Confirm client has tablet or PC with Chrome browser for My Cashmatic App (web) | readiness item |
| Inform client via email of first refill cash float amount required on installation date | confirmation, amount (amount field is **proposed**, not shown as an original separate field) |
| Set device configuration according to CDIG | step completion linked to detailed steps |
| Activate device following CDIG | step completion linked to detailed steps |
| Create three users (Admin, Manager, Staff) according to F2 | confirmation; **no passwords or credentials stored** |
| Ensure latest software/firmware update version | confirmation and version fields (see below) |
| Wrap/protect machine for delivery | checklist |
| Prepare electric/network cables, machine/cashbox keys and countertop installation equipment | checklist |
| Add remarks and photos for special customer installation | text/attachments |

### C. Configuration reference steps (p.2; preserve guidance, do not replace with one generic tick)
- Read CDIG pages 5-6.
- Set MAXIMUM LEVEL based on ideal setup and customer preference (F1).
- Set FLOAT LEVEL based on ideal setup and customer preference (F1).
- Set ACCEPTED DENOMINATIONS per customer preference.
- Program mail server for notification emails; CDIG page 8.
- Set printed notifications and choose wanted notifications.
- Set general device settings (name, language, etc.).
**Proposed structured values:** maximum amount, float amount, accepted denominations, notification configuration; exact choices/ranges must be verified from manufacturer/source.

### D. Activation reference steps (p.2; preserve instructional sequence)
- Read CDIG page 12.
- Open Reserved Area at cashmatic.eu/my-cashmatic.
- Create or access client account with client-authorized OTP; **never record OTP or passwords**.
- Registry Data -> All companies -> New -> customer activity.
- Use three-dots -> Pair Device to generate code (do not store code).
- Log in to device web panel with technician account.
- Open Device Management.
- Enter pairing code and install.
- Return to Reserved Area and confirm activation; verify notification.
**Design note:** Verification timestamp, actor and result should be captured; exact requirement to record step-by-step answers vs a guided procedure remains to be approved.

### E. Completed form data and evidence (p.3)
| Original PDF field | Proposed ERPNext/Frappe source |
|---|---|
| File Upload | permissioned attachments |
| Device | ERPNext Item (example in sample is Self Pay 460) |
| Serial Number | ERPNext Serial No, confirm matching Item and allocation |
| Software Update Version | entered data, record actual version |
| Firmware Update Version | entered data, record actual version |
| Activation Date | date/time entered/validated; confirmed against workflow |
| Employee Name | logged-in User/Employee reference |
| Phone Number | user/employee directory where available |
| Email | user email |
| Employee Signature | signed acknowledgment with audit identity |
| Additional Remarks | ordinary text **without credentials** |
| Special Installation Request | install type/notes + optional photos |
PDF special-install prompt mentions wall mounted, fixed on countertop, embedded under counter. Exact input choices/logic in Jotform builder still require confirmation.

**Security incident prevention:** The example PDF's Additional Remarks contains usernames/passwords. **Do not copy, retain or reprint these example credentials; remove credential text from reports, enforce controls to discourage/detect secrets in free text, and establish a safer admin-user provisioning process.** Treat the sample as sensitive.

### F. Customer working hours (p.4)
Seven rows Monday-Sunday with Open and Close times. Sample values are not product defaults. Proposed structured business-hours child table or location reference, confirm timezone/closed-days rule.

### G. Audit trail (p.5)
Submitted PDF has a completed status and signature event/time. Native Frappe must capture reliable user and submission/signoff timestamps, lifecycle history and report version. Do not reproduce third-party audit network/IP details without an explicit business need/privacy review.

### H. Fields proposed beyond original PDF (require approval)
Linked Sales Order/Subscription, customer, Contact, site Address, DeployOps Job, assigned Serial No, technician assignment, deployment planned date, status and reviewer outcome; per-step status including Blocked/NA; machine configuration amount fields and validation; required evidence for critical checks. These are **improvements**, not claims about the Jotform form.

## 2. Cashmatic On-site Installation — preliminary source headings
Original: https://form.jotform.com/253064644317254. Previously identified areas: machine positioning, power and network, first refill, customer training, key handover, POS integration, installation photographs and customer acceptance/signature. **Full field-by-field list, options, conditions and mandatory flags unverified; obtain completed PDF or builder export.**

Integration design: start from submitted Delivery Note (if sold), resolve customer/contact, Item and true serialized machine. Multi-machine deliveries have independent per-device outcomes. For rentals without Delivery Note, use linked deployment allocation and Subscription.

## 3. BellaBot Pro Pre-installation — preliminary source headings
Original: https://form.jotform.com/262743846222055. Previously identified areas: site assessment, route/passages measurements, navigation hazards, charging readiness, PUDU Cloud/account readiness, promotional content, mandatory photos and decision **GO / GO WITH CONDITIONS / NO GO**. **Verify all original fields and builder logic.**
Design: NO GO should block deployment pending documented resolution and authorized override; GO WITH CONDITIONS needs documented conditional approval policy (not yet approved).

## 4. BellaBot Pro On-site Installation — preliminary source headings
Original: https://form.jotform.com/262743396548066. Previously identified areas: physical condition, Wi-Fi/PUDU Link, mapping, operating modes, functional/safety tests, client training, evidence and signed handover. **Field-level mapping pending sample/builder export.**
Resolve machine identity from delivered physical Item/Serial No or active rental equipment assignment; never infer serial from Subscription service item.

## 5. Cashmatic Maintenance — preliminary source headings
Original: https://form.jotform.com/253383306590256. Previously identified component-level cleaning/inspection: banknote recycler, Cashbox, Pelicano and Smart Hopper, remarks and signatures. **Exact operations, options and mandatory flags pending sample/builder export.**
Use existing ERPNext Maintenance Visit/Schedule rather than an independently invented maintenance ticket.

## 6. Acceptance criteria for mapping work (#40)
- Table for **every** field: source section/label, type, option values, required, conditional trigger, validations, who enters, ERPNext reference/field, evidence, status and workflow implications.
- Screenshots/exports or redacted completed PDF for complex conditional/hidden sections.
- Explicit business decision record for any changed or removed original question.
- Product-owner sign-off per checklist before #22-#26 production implementation.
- No real credentials or personally identifying submissions committed to repository.

## 7. Outstanding questions
- Source builder exports or sample completed PDFs for the other four forms.
- Exact conditional rules and mandatory settings on all five Jotforms.
- ~~Reusable checklist template design vs dedicated Frappe native DocTypes (#20).~~ Decided 2026-10-20: one native DocType per checklist. The field lists read from the live Jotforms and the differences from them are in [CHECKLIST_ARCHITECTURE.md](CHECKLIST_ARCHITECTURE.md) §5.
- What evidence is mandatory for each risk-critical step.
- Signature and approval behavior, override rights and customer-facing report format.
