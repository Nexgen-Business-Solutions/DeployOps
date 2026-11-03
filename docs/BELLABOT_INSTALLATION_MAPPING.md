# BellaBot Pro On-site Installation — field mapping (#40, for #25)

**Status: DRAFT FOR PRODUCT-OWNER SIGN-OFF.** Each element of the original Jotform and the field in DeployOps that replaces it. Rows marked **Δ** differ from the source; §4 lists the differences that need your sign-off.

| | |
|---|---|
| Source | Jotform **BellaBot Pro - On-Site Installation & Commissioning**, https://form.jotform.com/262743396548066, read from the published form page on 2026-11-02 |
| Target | DocType **DeployOps BellaBot Installation** (`DO-BIN-.YYYY.-.#####`), `FORM_VERSION = 2` |

**What the published form shows:** labels, choices and required flags. **It has no conditional logic.** The builder's own settings were not available, so hidden rules, if any, are unverified.

## 1. Header (filled from the job)
Customer, address, machine, serial number, technician and company come from the job and the machine's row, and are read only, as on every checklist. This works the same for a sold machine (Delivery Note) and a rental machine (Subscription allocation).

## 2. Element by element
"q" is the Jotform question number. "Req" is the source's required flag.

| q | Source | Req | DeployOps | Note |
|---|---|---|---|---|
| 4, 6 | Customer Name, Site Address | yes | Customer, Address | **Δ** from the job |
| 5 | Site Name | yes | `site_name` | = |
| 7 | Technician Name | yes | Technician | **Δ** from the job |
| 8 | Installation Date and Time | yes | `installed_on` | = |
| 9, 10 | BellaBot Pro Model, Serial Number | yes | Machine, Serial number | **Δ** the job's ERPNext Item and Serial No |
| 12 | Deployment Type | yes | `deployment_type`, `deployment_type_other` | **Δ** choices in English; Other's text is required when chosen |
| 17 | Visible damage observed | yes | `visible_damage` | = |
| 24 | Note about damage | no | `damage_note` | **Δ** required with Moderate or Severe damage, §5 |
| 25 | Corrective action if applicable | no | `damage_corrective_action` | = |
| 20 | Arrival photos / evidence | yes | `arrival_photos`, 1 minimum | = |
| 28 | "Check": main power, Wi-Fi, PUDU Link app | yes | 3 required ticks | **Δ** one single choice in the source, see §4 |
| 34 | Power, network and PUDU Link setup notes | no | `setup_notes` | = |
| 151 | Deployment Manual PDF | – | Reference file, §3 | = |
| 36 | Map Name | yes | `map_name` | = |
| 38 | Localization / positioning checks + Other | yes | 3 ticks, `localization_other` | = a tick or the Other text |
| 40 | Map notes | no | `map_notes` | = |
| 141 | Operating Guide PDF | – | Reference file, §3 | = |
| 43 | Enabled modes | yes | 7 ticks | = |
| 55 | Mode notes | no | `mode_notes` | = |
| 53, 56, 59 | "Delivery / Cruise / Recycle tests and results" | – | section heading | **Δ** text elements with no answer |
| 54, 57, 60, 139 | Delivery, Cruise, Recycle, Birthday status | yes | `delivery_status`, `cruise_status`, `recycle_status`, `birthday_status` | = |
| 58 | Test notes | no | `test_notes` | **Δ** required when a mode test is Fail, §5 |
| 72 | Safety tests + Other | yes | 5 ticks, `safety_other` | = a tick or the Other text |
| 71 | Safety test overall result | yes | `safety_result` | = effects in §5 |
| 76 | Safety failure details | no | `safety_failure_details` | **Δ** required with FAIL, §5 |
| 79 | Advertising feature validation + Other | yes | 3 ticks, `advertising_other` | = a tick or the Other text |
| 80 | Audio announcement validation + Other | yes | 3 ticks, `audio_other` | = a tick or the Other text |
| 83 | Validation notes / failures | no | `validation_notes` | = |
| 85, 86, 87 | Training date, start and end time | date only | `training_date`, `training_start`, `training_end` | = |
| 88 | Training topics covered + Other | yes | 10 ticks, `training_topics_other` | = a tick or the Other text |
| 89 | Trainees attending | yes | `trainees` table, 1 minimum | **Δ** a table widget, see §4 |
| 101 | Maintenance reminders acknowledged + Other | yes | 2 ticks, `reminders_other` | = a tick or the Other text |
| 104 | Customer advisories provided + Other | yes | 5 ticks, `advisories_other` | = a tick or the Other text |
| 150 | Embedded image | – | Reference file, §3 | = |
| 107 | Photo(s) | yes | `installation_photos`, 1 minimum | = |
| 109 | Other installation evidence | no | `other_evidence` | = |
| 128 | Handover confirmed | yes | `handover_confirmed` | = effects in §5 |
| 130 | Acceptance date and time | yes | `accepted_on` | = |
| – | none | – | `customer_signatory` | **Δ** added: the name of who signs, see §4 |
| 132 | Customer signature | yes | `customer_signature` | = recorded with signer and time |
| 135 | Sign-off confirmation + Other | yes | 3 ticks, `sign_off_other` | = a tick or the Other text |
| 143 | Customer remarks | no | `customer_remarks` | **Δ** moved next to the customer signature; required with Handover = No, §5 |
| 136 | Technician signature | yes | `technician_signature` | = recorded with signer and time |
| 137 | Date and time | yes | `signed_off_on` | = |

Added on the DeployOps side: the signature record, the submitted snapshot, the job's audit trail, and the internal and customer PDF reports.

## 3. Reference files
Listed in **DeployOps Reference Files** for this checklist, and in `deployops/reference_files/`, so every site gets them automatically: on install, or on the next migrate for a site that already has the app. The files are the same ones the pre-installation checklist uses, compared by name and size for the PDFs and byte for byte for the image.

| File | Section | Source |
|---|---|---|
| `bellabot-deployment-manual.pdf` | Mapping and positioning | q151, BellaBot_Pro_Deployment_Manual |
| `bellabot-operation-guide.pdf` | Enabled modes | q141, BellaBot_Pro_Operation_Guide_V1.1-260409 |
| `bellabot-maintenance-and-care.png` | Customer advisories | q150, the form's embedded image |

## 4. Differences awaiting product-owner sign-off
| # | Difference | Proposal |
|---|---|---|
| 1 | The single-choice "Check" is three required ticks | As a single choice, the source lets a technician confirm only one of power, Wi-Fi and the PUDU Link app. All three are needed for a working robot |
| 2 | Customer name added for the customer signature | The source doesn't record who signed |
| 3 | Trainees are a table | Each trainee is one row, instead of the source's table widget |
| 4 | Deployment types are in English | The source's are in French. The app is English only |

## 5. Decisions (product owner, 2026-11-02)
| Answer | Effect |
|---|---|
| Safety test overall result = FAIL | Details required. Submitting blocks the machine, with the details as the reason, so the job can't go to review. A Supervisor or Manager in scope clears it with **Unblock Machine**, which then needs a reason |
| Handover confirmed = No | Customer remarks required. Blocks the machine the same way, with the remarks as the reason |
| A mode test = Fail | Test notes required. The machine isn't blocked |
| Moderate or Severe damage | The damage note is required. The machine isn't blocked |

Everything is written to the job's Status Log. "Not Tested" needs no notes. Issue #15 (commercial triggers) stays open and doesn't block this checklist (owner decision, 2026-11-02).
