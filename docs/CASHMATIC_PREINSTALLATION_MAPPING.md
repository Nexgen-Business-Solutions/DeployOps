# Cashmatic Pre-installation — field mapping (#40, for #22)

**Status: DRAFT FOR PRODUCT-OWNER SIGN-OFF.** This document lists each element of the original Jotform and the field in DeployOps that replaces it. Rows marked **Δ** differ from the source. Each Δ needs the product owner's decision (§4). Until sign-off, the DocType is the working proposal, not an approved specification.

| | |
|---|---|
| Source | Jotform **Pre-Visit-Installation Checklist**, https://form.jotform.com/253063954693264, read from the published form definition on 2026-10-24 (26 elements) |
| Target | DocType **DeployOps Cashmatic Pre-installation** (`DO-CPI-.YYYY.-.#####`), `FORM_VERSION = 1` |
| Also seen | Completed PDF sample (see CHECKLIST_SPECS.md §1). It contains customer data and credentials and is **not** in the repository |

**What the source form defines:** labels, choices, required flags and minimum selections. **No conditional logic.** No field is shown or hidden based on another answer, so DeployOps has no `depends_on` on this form either.

## 1. Header (no source equivalent, filled from the job)
| DeployOps field | Value | Note |
|---|---|---|
| Job, Job machine row | the DeployOps Job and its device row | the form exists once per machine |
| Customer, Address | from the job's ERPNext source | read only |
| Machine, Machine name | ERPNext Item on the device row | read only |
| Serial number | ERPNext Serial No on the device row | read only; a draft follows the job's serial; **submit is refused until the machine has a serial**; frozen once submitted |
| Technician, Company | from the job | read only |
| Form version | 1 | stamped; a form started on an older version can't be submitted |

## 2. Element by element
Source types: *checkbox*, *textbox*, *dropdown* and so on are Jotform types. "Req" is the source's required flag.

| # | Source element (type, req) | DeployOps field (type, required) | | Note |
|---|---|---|---|---|
| 1 | Heading "Pre-Visit-Installation Checklist", sub "Please complete the following checklist one week before installation date." | Form title + intro text | = | intro wording kept |
| 2 | Animated heading "Self Pay 460" (widget) | Header **Machine name** | Δ1 | the model now comes from the job's Item, so the form isn't specific to the SP460 |
| 3 | **Shared Documents Prior To The Visit** (checkbox, req, min 4 of 4) | Section *Shared documents prior to the visit*: 4 Check fields, each required | = | wording: "Self Pay460" → "Self Pay 460" |
| 4 | PDF "Web Interface" (Cashmatic-Web-Interface.pdf) | Reference file **Web panel interface**, same section | = | see §3 |
| 5 | PDF labelled "User Manual SP460" (460-ENG-User manual.pdf) | Reference file **Self Pay 460 user manual**, same section | = | |
| 6 | PDF labelled "User Manual SP460" (EN-MyCashmaticApp.pdf) | Reference file **My Cashmatic App**, same section | Δ2 | the source labels this file "User Manual SP460"; it's the My Cashmatic App guide, so it's titled by its content |
| 7 | **Employee Checklist** (checkbox, req, min 12 of 12) | Section *Employee checklist*: 12 Check fields, each required | = | wording tidied (e.g. "chrome explorer" → "Chrome", "CDIG. ." → "the CDIG"); meaning unchanged |
| 8 | **Machine Configuration Steps** (checkbox, req, min 7 of 7) | Section *Machine configuration steps*: 7 Check fields, each required | = | covers CDIG pp. 5–6, MAXIMUM LEVEL (F1), FLOAT LEVEL (F1), ACCEPTED DENOMINATIONS, mail server (CDIG p. 8), PRINTED NOTIFICATIONS, GENERAL DEVICE SETTINGS |
| 9 | **Machine Activation Steps** (checkbox, req, min 9 of 9) | Section *Machine activation steps*: 9 Check fields, each required | = | typos fixed ("optaining", "ISTALL"). The OTP and pairing code are **never recorded**; text like `OTP: …` or `pairing code = …` is refused |
| 10 | PDF "For more clarification on SP460 Activation review CDIG page12." (Cashmatic installation guide.pdf) | Reference file **Cashmatic Device Installation Guide (CDIG)** in *Machine configuration steps* and *Machine activation steps* | = | also shown under configuration, which cites CDIG pp. 5–8 |
| 11 | PDF "For more clarification about SP460 parts." (EN user manual self pay 460 (3).pdf) | Reference file **Self Pay 460 parts (user manual)** in *Machine activation steps* | = | bundled as `parts-manual.pdf` (#42 follow-up); it was missing from the bundled list |
| 12 | PDF "Client device configuration SP460 - F1" | Reference file **F1 client device configuration** in *Machine configuration steps* | = | the source shows it after the activation steps; DeployOps shows it where the F1 steps are |
| 13 | PDF "User access configuration - F2" | Reference file **F2 user access configuration** in *Employee checklist* | = | next to "Create 3 users … (F2)" |
| 14 | **File Upload** (fileupload, req), "Proof of machine preparation (After Setup / Ready for delivery)." | Section *Proof of machine preparation*: **Photos** table, at least 1 | Δ3 | photos only (images); any file in the source. Files are private and attached to the form |
| 15 | **Device** (dropdown, req): Self pay 460, … 460 with coins drawer, Self pay 1060, … 1060 with coins drawer, Visual pay 27 counter top / wall mounted / with stand / with 460, Visual Pay 22 counter top / wall mounted / with stand | **Device** (Data, read only), fetched from the Item name | Δ4 | the model is the ERPNext Item, picked on the order and the job. The **mounting variant** (counter top, wall, stand) and **coins drawer** aren't a choice here |
| 16 | **Serial Number** (textbox, req) | Header **Serial number** (Link to Serial No, from the job) | Δ5 | not typed on the form. It must be an ERPNext serial of that Item, reserved for this job; required before submit |
| 17 | **Software Update Version** (textbox, req) | **Software version** (Data, required) | = | |
| 18 | **Firmware Update Version** (textbox, req) | **Firmware version** (Data, required) | = | |
| 19 | **Activation Date** (date + time, req) | **Activation date** (Datetime, required) | = | |
| 20 | **Employee Name** (full name, req) | Header **Technician** (User, from the job) + signer recorded with the signature | Δ6 | not typed; it's the signed-in, assigned technician |
| 21 | **Phone Number** (phone, optional) | — | Δ6 | dropped; the User record holds contact details |
| 22 | **Email** (email, optional) | — | Δ6 | dropped; it's the User's email |
| 23 | **Employee Signature** (signature, req) | **Employee signature** (Signature, required) | = | the server also records signer, time and capturing user; the snapshot keeps them |
| 24 | **Additional Remarks** (text area, req) | **Additional remarks** (Small Text, required) | = | text like `password: …` or `PIN = …` is refused (the PDF sample had credentials here). It's a pattern check: it doesn't catch every secret |
| 25 | **Special Installation Request: (Wall mounted / Fixed on Counter Top / Embeded Under Counter)** (rich-text editor with images, req) | **Special installation request** (Small Text, required) | Δ7 | plain text; **no image insert**, though Employee checklist step 12 says "attach example photos" |
| 26 | **Cutomer Working Hours** (matrix, req): rows Monday–Sunday; columns Open, Close; each cell a dropdown of 24 whole hours (12 AM … 11 PM) | **Working hours** table, fixed rows Monday–Sunday: Open (Time), Close (Time), **Closed** (Check) | Δ8 | any time, not whole hours only; a day needs both times **or** Closed. The source has no "Closed" choice |

Added on the DeployOps side (not in the source): Submitted snapshot (answers, labels, form version, signature records) and the job's audit trail. They replace the Jotform audit page (PDF p. 5) without recording IP/network details.

## 3. Reference files
The PDFs embedded in the Jotform are listed in **DeployOps Reference Files** and shown under their section and in "Documents for this checklist". The bundled names are in `deployops/reference_files/README.md`. The PDFs themselves are **not** committed: they are Cashmatic/Massarie material, and whether they may be put in the repository is open (Q9). An administrator uploads them on the site.

The Massarie logo (machine labeling, Employee checklist step 1) is a DeployOps addition; it's not embedded in the source.

## 4. Decisions needed from the product owner
| Δ | Question | Current behaviour (proposal) |
|---|---|---|
| Δ1 | Is one Cashmatic pre-installation form right for all models (SP460, SP1060, Visual Pay 22/27), or are some steps model-specific (e.g. coins drawer, Visual Pay)? | One form; step wording still says "Self Pay 460" where the source does |
| Δ2 | OK to title the third PDF "My Cashmatic App" instead of the source's "User Manual SP460"? | Titled by content |
| Δ3 | Proof of preparation: photos only, or also other files (PDF, video)? Is one enough? | Photos, at least 1 (the source's minimum) |
| Δ4 | Where should the **mounting variant** (counter top / wall / stand / embedded) and **coins drawer** be recorded: separate Items, a Select field on this form, or the special-installation text? | Item for model; mounting in the special-installation text |
| Δ5 | Confirm: the serial comes from the job (ERPNext Serial No) and can't be typed on the form | As stated |
| Δ6 | Confirm dropping employee phone/email, and taking the name from the signed-in technician | As stated |
| Δ7 | Special installation request: should it take example photos (step 12 asks for them)? Should it be a choice (Wall mounted / Counter top / Embedded under counter / None) plus notes, instead of free text only? Should it stay required when there's no special request? | Required free text, no photos |
| Δ8 | Working hours: is "Closed" acceptable? Whole hours only, or any time? Overnight hours (close after midnight)? Is the timezone the site's? | Times or Closed per day; any time; no overnight check |
| Q9 | May the Cashmatic/Massarie PDFs be committed to the repository, or are they uploaded per site only? | Uploaded per site; bundled filenames listed |
| Q10 | The source's "Activate the device" (Employee checklist) and the 9 activation steps say the same thing twice. Keep both, as in the source? | Kept both |

## 5. Sign-off
| Role | Name | Decision | Date |
|---|---|---|---|
| Product owner | | | |
