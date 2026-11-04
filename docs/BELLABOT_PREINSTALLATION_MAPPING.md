# BellaBot Pro Pre-installation — field mapping (#40, for #24)

**Status: DRAFT FOR PRODUCT-OWNER SIGN-OFF.** Each element of the original Jotform and the field in DeployOps that replaces it. Rows marked **Δ** differ from the source; §4 lists the differences that need your sign-off.

| | |
|---|---|
| Source | Jotform **BellaBot Pro - Pre-Installation & Site Readiness Assessment**, https://form.jotform.com/262743846222055, read from the published form page on 2026-11-01 (56 elements) |
| Target | DocType **DeployOps BellaBot Pre-installation** (`DO-BPI-.YYYY.-.#####`), `FORM_VERSION = 2` |

**What the published form shows:** labels, choices, required flags and hints. **No conditional logic is visible** on the page. The builder's own settings were not available, so hidden rules, if any, are unverified.

## 1. Header (filled from the job)
Customer, address, machine, serial number, technician and company come from the job and the machine's row, and are read only, as on every checklist.

## 2. Element by element
"q" is the Jotform question number. "Req" is the source's required flag.

| q | Source | Req | DeployOps | Note |
|---|---|---|---|---|
| 4, 131 | Customer / Company Name, Address | yes | Customer, Address | **Δ** from the job |
| 5 | Site / Branch Name | yes | `site_name` | = |
| 6 | Planned Installation Date | yes | `planned_installation_date` | = |
| 7 | Robot Model | yes | Machine | **Δ** the job's ERPNext Item |
| 121 | PID Robot | yes | `pid_robot` | = |
| 112 | Options (Purchase, Rental, Financing) + Required Action + Due Date | no | `commercial_actions` table | = |
| 9 | Intended use case + Other | yes | `intended_use`, `intended_use_other` | = Other's text is required when chosen |
| 10 | Primary functions required + Other | no | 6 ticks, `primary_functions_other` | = |
| 13, 14, 15 | Indoors, floors dry, humid or wet area | yes | `site_indoors`, `floors_dry`, `humid_area` | = |
| 16 | Site environment comments | no | `site_environment_comments` | = |
| 18 | Two-way traffic planned | yes | `two_way_traffic` | = |
| 19, 20 | Narrowest passage, kitchen entrance (cm; hint "minimum 65 cm") | yes | `narrowest_passage_cm`, `kitchen_entrance_cm` | = 0 to 500 enforced as in the source; the hint is guidance, see §4 |
| 118, 21 | Maximum dish size, two-way corridor width (cm) | no | `max_dish_size_cm`, `two_way_corridor_cm` | = 0 to 500 enforced as in the source |
| 22 | Slope (degrees) - MAX 5 | yes | `slope_degrees` | = 0 to 90 enforced as in the source; the 5° is guidance, see §4 |
| 24 | Stairs on the route | yes | `stairs_on_route` | = |
| 26 | Hazard Type + Other | yes | `hazard_type`, `hazard_type_other` | = single choice as in the source |
| 27 | Surface conditions around sensor height | no | 5 ticks | = |
| 29 | Corrective actions required + Other | no | 6 ticks, `corrective_actions_other` | = |
| 30 | Corrective notes | no | `corrective_notes` | = |
| 113 | Map/table number (files) | no | `route_map_files` | = |
| 37, 39 | Team charges the robot, charger uses AC power | yes | `team_charges_robot`, `aware_charger_ac` | = |
| 52 | Promotional screen used and client contacted | yes | `promo_screen` | = |
| 53 | Content types ready for upload | yes | 4 ticks, at least one | **Δ** only when the screen is used, see §4 |
| 54 | "Content format requirements" | – | none | **Δ** a text element with no answer |
| 55 | Upload advertising files | no | `advertising_files` | **Δ** only when the screen is used |
| 116 | PUDU Cloud: store created, restricted user configured | no | 2 ticks | = |
| 117 | User: "email" and "password" boxes | no | `pudu_cloud_user` | **Δ** no password is stored, see §4 |
| 59 | Scheduled shipping date | no | `shipping_date` | **Δ** a date; a number box in the source |
| 60 | Estimated shipping costs ($) | no | `shipping_cost` | **Δ** currency of the company |
| 58 | Delivery and access notes | no | `delivery_notes` | = |
| 64 | Operating days | yes | 7 ticks, at least one | = |
| 65, 66 | Daily opening and closing time | yes | `opening_time`, `closing_time` | = |
| 73 | Documents shared + Other | no | 6 ticks, `documents_shared_other` | = "Manuel" corrected to "manual" |
| 130, 129, 127, 128 | Deployment manual, operation guide, product introduction PDFs; maintenance and care image | – | Reference files, §3 | = |
| 78, 80 | Primary operating area, route and obstacle photos | yes | `operating_area_photos`, `route_photos`, 1 minimum each | = |
| 82 | Special requirements + Other | no | 6 ticks, `special_requirements_other` | = |
| 83 | Installation constraints or site notes | no | `installation_constraints` | = |
| 84 | Can the installation proceed | yes | `can_proceed` | = |
| 87 | Unresolved hazards / warnings + Other | no | 6 ticks, `unresolved_hazards_other` | = |
| 92 | Additional risk notes | no | `risk_notes` | = |
| 94 | Final Decision | yes | `final_decision` | = effects in §5 |
| 95 | Decision remarks | no | `decision_remarks` | **Δ** required with NO GO and GO WITH CONDITIONS, §5 |
| 100 | Employee Name | yes | Technician | **Δ** from the job |
| 103 | Employee Signature | yes | `employee_signature` | = recorded with signer and time |

The page also holds leftover translations for fields that aren't on the published form, such as "Reinspection Date", "Decision Basis" and "Outstanding Corrective Actions". They are not included.

Added on the DeployOps side: the signature record, the submitted snapshot, the job's audit trail, and the internal and customer PDF reports.

## 3. Reference files
Listed in **DeployOps Reference Files** under *Documents shared before installation*, and in `deployops/reference_files/`, so every site gets them automatically: on install, or on the next migrate for a site that already has the app.

| File | Source |
|---|---|
| `bellabot-deployment-manual.pdf` | BellaBot_Pro_Deployment_Manual |
| `bellabot-operation-guide.pdf` | BellaBot_Pro_Operation_Guide_V1.1-260409 |
| `bellabot-product-introduction.pdf` | Product_introduction_to_BellaBotPro |
| `bellabot-maintenance-and-care.png` | The form's embedded image: sections 5.1 and 5.2 of a manual |

## 4. Differences awaiting product-owner sign-off
| # | Difference | Proposal |
|---|---|---|
| 1 | The 65 cm minimum and the 5° maximum are guidance, not refusals | The source only shows them as hints. The technician reflects a failed limit in the decision |
| 2 | Content types and advertising files appear only when the promotional screen is used | The source always requires content types, which makes no sense for a site with no screen |
| 3 | PUDU Cloud user name only | The source has a password box. The project never stores passwords in a checklist |

## 5. Decisions (product owner, 2026-11-01)
| Final decision | Effect on the machine |
|---|---|
| GO | None |
| NO GO | Remarks required. Submitting blocks the machine, with the remarks as the reason, so the job can't go to review. A Supervisor or Manager in scope clears it with **Unblock Machine**, which then needs a reason |
| GO WITH CONDITIONS | Remarks required. The machine keeps its status, and **Complete Machine** is refused until a Supervisor or Manager in scope uses **Approve Conditions**. A replacement form needs a new approval |

Everything is written to the job's Status Log.
