# Cashmatic Pre-installation — UAT scenarios (#22)

Hand-run scenarios for accepting the pre-installation checklist on the test site (`deployops.local`). Each one matches a requirement of #22 and an automated test in `deployops/tests/test_cashmatic_preinstallation.py`. Setup (Item, serials, roles, equipment access, order, job) follows [CASHMATIC_PREINSTALLATION_QUICKSTART.md](CASHMATIC_PREINSTALLATION_QUICKSTART.md). Use test data only: no real customers, and never real passwords or codes.

**Before you start:** a submitted Sales Order with **two** Cashmatic machines; a Pre-installation job from it, assigned to the test technician, **started** (In Preparation), with a serial on machine 1 only; the reference PDFs uploaded in **DeployOps Reference Files** (see `deployops/reference_files/README.md`).

Record each result as Pass / Fail with the date, the tester and, for a Fail, what happened.

| # | Requirement | Steps | Expected | Automated test |
|---|---|---|---|---|
| U1 | Documents to share before the visit | As the technician, open `/deployops` → Cashmatic Pre-installation → the job → machine 1 → Start → Start checklist | "Documents for this checklist" lists the manuals; section 1 shows 4 steps with the Web panel, Self Pay 460 manual and My Cashmatic App cards. **Read** opens the viewer; pages turn | `test_reference_manuals_are_bundled_for_real_sections_of_the_form`, `test_reference_files.py` |
| U2 | Readiness, labeling, accessories | Look at section 2 | 12 steps, including logo and QR code, area clear, electrical plug, tablet/PC with Chrome, first refill email, wrap and protect, cables/keys/counter top accessories; F2 and logo cards | `test_every_source_step_is_a_required_tick_in_its_section` |
| U3 | CDIG / F1 configuration: maximum, float, denominations, email and printed notifications | Look at section 3 | 7 steps with CDIG and F1 cards | same |
| U4 | Activation | Look at section 4 | 9 steps with CDIG and SP460 parts cards; the section note says never to type passwords, OTPs, PINs or pairing codes | same |
| U5 | Every step counts | Tick everything except one step, fill the rest, Submit | Submit is refused; the unticked step is marked and the page scrolls to it | `test_each_unticked_step_stops_the_submit` |
| U6 | Software / firmware / activation date | Leave Software version empty, Submit | Refused, "Software version" marked. Fill it, firmware and the activation date and time | `test_machine_details_evidence_hours_remarks_and_signature_are_required` |
| U7 | Device | Look at "Device" | The machine's Item name; can't be edited | `test_device_comes_from_the_item_on_the_job` |
| U8 | Proof photo | Submit with no photo, then add one | Refused without; accepted with one. The photo URL opened in a private window (signed out) is refused | `test_preparation_photos_must_be_private_files_of_this_form` |
| U9 | Customer working hours | Fill Monday–Saturday with times, tick Closed on Sunday; then clear Monday's closing time and Submit | Seven fixed days. A day needs open and close times or Closed; Monday is marked | `test_seven_fixed_days_each_open_and_close_or_closed` |
| U10 | Special installation request | Type e.g. "Wall mounted, left of the counter" | Saved; required to submit | `test_machine_details_…_are_required` |
| U11 | No credentials | Type `password: test123` in Additional remarks; then `OTP = 123456` in the special request | Both refused with "do not enter passwords, PINs, OTPs or pairing codes" | `test_no_credentials_or_activation_codes_in_text` |
| U12 | Signature | Sign as the employee, fill the remarks, Submit | Submitted; the form is locked with "Submitted on … by …". In Desk, the signature record shows the technician's name, time and user. A supervisor can no longer change this machine's serial on the job | `test_submit_locks_the_form_with_signer_snapshot_and_serial` |
| U13 | Serial before preparation completes | Machine 2 (no serial): Start, Start checklist, fill everything, Submit; then try **Complete Machine** | The app warns the machine has no serial; Submit and Complete are both refused. Supervisor picks a serial in Desk; the draft shows it on reload; Submit and Complete now work | `test_serial_is_assigned_before_preparation_completes` |
| U13b | Checklist before completion | Machine 1: Start Machine, then **Complete Machine** before submitting its checklist | Refused: "Submit the checklist of machine … before completing it". After the checklist is submitted, Complete works | `test_a_machine_completes_only_once_its_checklist_is_submitted` |
| U14 | Two machines, separate outcomes | Look at the job after U12 and before U13's serial | Machine 1 submitted, machine 2 still open: each has its own checklist | `test_two_machines_on_one_order_get_their_own_checklists` |
| U15 | Who can see it | Open the checklist URL as another technician (not on the job) and as a guest | Refused for both; the supervisor and manager in scope can open it | `test_only_people_on_the_job_can_read_the_form` |
| U16 | Approval | Complete both machines, Submit for Review; as supervisor, Approve | Job Completed; both checklists locked with their snapshots | `test_release_scenarios.py::TestSale` |
| U17 | Phone | Repeat U1, U5 and U12 on a phone-sized window | Usable without horizontal scrolling; viewer pages fit the width | manual only |

## Not covered yet (open)
- Field mapping differences awaiting product-owner decisions: [CASHMATIC_PREINSTALLATION_MAPPING.md §4](CASHMATIC_PREINSTALLATION_MAPPING.md).
- No printable report of the submitted checklist yet (#27).
