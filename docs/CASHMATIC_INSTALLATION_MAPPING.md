# Cashmatic On-site Installation — field mapping (#40, for #23)

**Status: DRAFT FOR PRODUCT-OWNER SIGN-OFF.** This document lists each element of the original Jotform and the field in DeployOps that replaces it. Rows marked **Δ** differ from the source. Each Δ needs the product owner's decision (§4). Until sign-off, the DocType is the working proposal, not an approved specification.

| | |
|---|---|
| Source | Jotform **On Site - Installation Checklist**, https://form.jotform.com/253064644317254, read from the published form page and its widget settings on 2026-10-31 |
| Target | DocType **DeployOps Cashmatic Installation** (`DO-CIN-.YYYY.-.#####`), `FORM_VERSION = 1` |
| Also seen | No completed sample of this form |

**What the published form defines:** labels, choices, required flags and minimum selections. The published page has **no conditional logic**. Rules kept only in the Jotform builder can't be seen from it.

## 1. Header (no source equivalent, filled from the job)
| DeployOps field | Value | Note |
|---|---|---|
| Job, Job machine row | the DeployOps Job and its device row | the form exists once per machine |
| Customer, Address | from the job's ERPNext source | read only |
| Machine, Machine name | ERPNext Item on the device row | read only |
| Serial number | ERPNext Serial No on the device row | read only; for a sale, it comes from the Delivery Note |
| Technician, Company | from the job | read only |
| Form version | 1 | stamped; a form started on an older version can't be submitted |

## 2. Element by element
Source types are Jotform types. "Req" is the source's required flag. The `q` number is the Jotform question ID.

| # | Source element (type, req) | DeployOps field (type, required) | | Note |
|---|---|---|---|---|
| 1 | Heading "On Site - Installation Checklist", sub "Please complete the following checklist before Leaving the site." | Form title + intro text | = | title comes from the card, "Cashmatic Installation" |
| 2 | q32 Animated Heading widget | Header **Machine name** | Δ1 | the model comes from the job's Item |
| 3 | q48 **Machine Positioning Evaluation** (checkbox, req, min 8 of 8) | Section *Machine positioning evaluation*: 8 Check fields, each required | = | wording tidied ("Pe-Visit" → "pre-visit") |
| 4 | q85 PDF "Pre & Post Installation (V-PP-V-1.0)" (Cashmatic installation guide.pdf) | Reference file **CDIG** in the same section | Δ2 | the source shows the CDIG under this title |
| 5 | q51 **Power and Network** (checkbox, req, min 5 of 5) | Section *Power and network*: 5 Check fields, each required | = | |
| 6 | q117, q59 **Type of Network** (dropdown, req: Wi-Fi, Ethernet cable), each followed by q61, q115 **IP** (textbox, req); q114 a third **Type of Network** after the Submit button | **Type of network** (Select, required), **IP address** (Data, required), once each | Δ3 | |
| 7 | q68 PDF "If the following steps are not clear, Scan QR code on CDIG page 14 for video tutorial if needed." (same file) | Reference file **CDIG** in *Power and network*, and the section note | = | |
| 8 | q62 **Verifications** (checkbox, req, min 2 of 2) | Section *Verifications*: 2 Check fields, each required | = | |
| 9 | q65 **Verify Software update**, q66 **Verify Firmware update** (textbox, req) | **Software version**, **Firmware version** (Data, required) | = | |
| 10 | Heading **Preparing the Machine**; q130 (checkbox, req, min 4 of 4) | Section *Preparing the machine*: 4 Check fields, each required | = | |
| 11 | q129 **CashBOX** (dropdown, optional: 500 Banknote, 1000 banknote) | **CashBOX** (Select, optional) | = | |
| 12 | q69 steps with no heading (checkbox, req, **min 8 of 9**) | Section *Customer training*: 9 Check fields, **each required** | Δ4 | heading added; typos fixed |
| 13 | q121 **Keys Receiver Name** (full name, req), q124 **Signature** (req), q123 **Date** (req), under "Key Handover Confirmation" | Section *Key handover confirmation*: **Keys receiver name** (Data), **Keys receiver signature**, **Handover date**, all required | Δ5 | one name field; shown near the end of the form, not after training |
| 14 | q86 PDF "Web Panel Interface" (Cashmatic-Web-Interface.pdf) | Reference file **Web panel interface** in *Web panel explanation* | = | |
| 15 | q87 PDF "My Cashmatic App" (EN-MyCashmaticApp.pdf) | Reference file **My Cashmatic App** in *Web panel explanation* | = | |
| 16 | q104 **Web Panel Explaination** (checkbox-in-dropdown widget, req, 12 options, hint "Explain All Options") | Section *Web panel explanation*: 12 Check fields, tick at least one | Δ6 | |
| 17 | q105 **Firsthand Training** (same widget, req, 13 options, hint "The customer must know how to ...") | Section *Firsthand training*: 13 Check fields, tick at least one | Δ6 | typos fixed ("Dinomination", "indentify") |
| 18 | q106 **Problem Solving** (same widget, req, 3 options + a fourth "Support contact" option) | Section *Problem solving*: 3 Check fields, tick at least one; support contact in the section note | Δ6 | the contact isn't a step, so it can't be ticked |
| 19 | q107 **WARNINGS/PRECAUTIONS** (same widget, req, 4 options) | Section *Warnings and precautions*: 4 Check fields, tick at least one | Δ6 | |
| 20 | q131 PDF (Warnings & Precautions.pdf) | Reference file **Warnings and precautions**, same section | = | new file name `warnings-precautions.pdf` |
| 21 | q88 **POS integration** (dropdown, req: Yes, No) | **POS integration** (Select, required) | = | |
| 22 | q89 **If Yes, POS brand / version** (textbox, req), q90 **API / App connector required** (textbox, req) | **POS brand / version**, **API / app connector required** (Data), shown and required only when POS integration = Yes | Δ7 | the source requires them always, though the label says "If Yes" |
| 23 | q14 **Photos of Installation** (file upload, req, at least 3) | **Photos of installation** table, at least 3 | = | images only; private files attached to the form |
| 24 | q33 **Machine**, q76 **Serial Number** (textbox, req) | Header **Machine**, **Serial number** (from the job) | Δ1 | not typed on the form |
| 25 | q29 **Date & Time of Installation** (widget, req) | **Date and time of installation** (Datetime, required) | = | |
| 26 | q42 **Codition at Delivery** (textbox, req) | **Condition at delivery** (Data, required) | = | typo fixed |
| 27 | q73 **Client Representative** (textbox, req) | **Client representative** (Data, required) | = | |
| 28 | q72 **Technician Name** (textbox, req) | Header **Technician** (from the job) | Δ1 | not typed |
| 29 | q82 **Title**, q110 **Department** (textbox, req) | **Title**, **Department** (Data, required), read as the client representative's | Δ8 | |
| 30 | q22, q113 **Signature** (signature, optional, both unnamed) | **Client representative signature** (required), **Technician signature** (optional) | Δ8, Δ9 | the customer signature is the machine's acceptance, one per machine |
| 31 | q6 **Remarks** (text area, optional) | **Remarks** (Small Text, optional) | = | text like `password: …` or `PIN = …` is refused |

Added on the DeployOps side (not in the source): the signature record, the submitted snapshot, the job's audit trail and the internal and customer PDF reports.

## 3. Reference files
Each PDF embedded in the Jotform is listed in **DeployOps Reference Files** for this checklist and shown under its section. The list is seeded only on a fresh install, so a site that already has a list needs its administrator to add these rows and upload the two new PDF slots. `deployops/reference_files/README.md` has the file names.

The PDFs are not added to the repository by this change, because whether they may be committed is still open (pre-installation mapping, Q9).

## 4. Decisions needed from the product owner
| Δ | Question | Current behaviour (proposal) |
|---|---|---|
| Δ1 | Confirm: machine, serial and technician come from the job and can't be typed | As stated |
| Δ2 | Is "Visual – Pre and Post Installation (V-PP-V-1.0)" the CDIG, or a separate document? The first step tells the technician to follow it | The CDIG is shown there, as in the source |
| Δ3 | The source asks for network type and IP twice. Can one machine need two connections? | One network type and one IP |
| Δ4 | The source accepts 8 of the 9 customer-training steps without saying which may be skipped. Must all 9 be done? | All 9 required |
| Δ5 | Keep key handover after training and sign-off data, or move it right after training as in the source? | Near the end |
| Δ6 | The hints say "Explain All Options" and "must know", but the source accepts one tick per list. Should every item be required? | At least one, as in the source |
| Δ7 | POS brand and connector only when POS integration = Yes? | Only when Yes |
| Δ8 | The source's two signatures have no names. Are they the client representative and the technician, and are Title and Department the representative's? | As stated |
| Δ9 | #23 lists a customer signature and machine-level acceptance, but the source's signature is optional. Owner's decision, 2026-10-31: required, and machine-level acceptance is the customer signing each machine's form. To confirm with the product owner: the supervisor still approves the whole job, not each machine | Required on each machine's form |
| Δ10 | The step "Confirm reviewing notes for Special installation Request" refers to the pre-installation checklist, which the on-site form doesn't show. Should its notes appear on this form? It may be another technician's job | Not shown; the step is a tick only |
| Δ11 | #23 and the functional spec start an on-site installation from a Delivery Note, but an Installation job can also be created from a Sales Order with nothing delivered yet. Should that be refused? | Allowed |

## 5. Sign-off
| Role | Name | Decision | Date |
|---|---|---|---|
| Product owner | | | |
