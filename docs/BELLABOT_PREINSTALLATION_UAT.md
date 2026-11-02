# BellaBot Pre-installation — UAT scenarios (#24)

Hand-run scenarios for accepting the checklist on the test site. Each one matches a requirement of #24 and an automated test in `deployops/tests/test_bellabot_preinstallation.py`. Use test data only: no real customers, and never real passwords or codes.

**Before you start:** a Sales Order for **two** BellaBot machines; a Pre-installation job from it, assigned to the test technician, started by a Supervisor, with a serial on each machine; the reference files listed in **DeployOps Reference Files** for this checklist (see `deployops/reference_files/README.md`).

Record each result as Pass / Fail with the date, the tester and, for a Fail, what happened.

| # | Requirement | Steps | Expected | Automated test |
|---|---|---|---|---|
| U1 | Other answers | Choose Intended use = Other, leave the text empty, Submit; do the same for Hazard type | Refused until the text is filled in | `test_other_is_a_choice_that_needs_its_text` |
| U2 | Documents | Open the checklist as the technician | The deployment manual, operation guide, product introduction and maintenance and care files are listed and open in the viewer | `test_every_source_document_ships_with_the_app_in_a_real_section` |
| U3 | No credentials | Type `password: test123` in PUDU Cloud user | Refused with "do not enter passwords, PINs, OTPs or pairing codes" | `test_no_credentials_in_the_pudu_cloud_details` |
| U4 | Remarks | Choose NO GO, then GO WITH CONDITIONS, with no remarks; Submit | Refused both times. With GO, remarks aren't needed | `test_no_go_and_conditions_need_remarks`, `test_go_needs_no_remarks` |
| U5 | GO | Machine 1: submit GO, Start Machine, Complete Machine | Completed | `test_go_leaves_the_machine_free_to_complete` |
| U6 | NO GO blocks | Submit NO GO with remarks; try Submit for Review | The machine is Blocked, the Status Log shows the remarks, and the job is refused | `test_submitting_no_go_blocks_the_machine_with_the_remarks_as_reason`, `test_the_job_cannot_go_to_review` |
| U7 | Clearing a NO GO | As the technician, look for Unblock Machine. As a Supervisor, Unblock with no reason, then with one | Technician can't. Supervisor is refused with no reason, then the machine goes to In Progress and the reason is logged | `test_the_technician_cannot_clear_it`, `test_clearing_needs_a_reason_and_is_logged` |
| U8 | Conditions wait | Submit GO WITH CONDITIONS with remarks; Start Machine; Complete Machine | Complete is refused until the conditions are approved | `test_complete_is_refused_until_approved` |
| U9 | Approving | As the technician, look for Approve Conditions. As a Supervisor, Update Machine → Approve Conditions; then Complete Machine | Technician can't. The job's machine row shows who approved and when, the Status Log has the entry, and the machine completes | `test_the_technician_cannot_approve`, `test_approval_records_who_and_when_then_the_machine_completes` |
| U10 | Scope | As a Supervisor without BellaBot in their equipment profile, try to open the job | Refused | `test_out_of_scope_supervisor_cannot_clear_it`, `test_out_of_scope_supervisor_cannot_approve` |
| U11 | Replacement form | As a Manager, cancel an approved GO WITH CONDITIONS form; start and submit a new one the same way | Approval is needed again | `test_a_new_form_needs_a_new_approval` |
| U12 | Two machines | Machine 1 NO GO, machine 2 GO | Machine 1 is Blocked, machine 2 isn't | `test_each_machine_has_its_own_outcome` |
| U13 | Reports | On a submitted checklist, open **Report (PDF)** and **Customer copy (PDF)**. In Desk, Print with **BellaBot Pre-installation Report** | Both open with the decision and its remarks | `TestReport` |

## Not covered yet (open)
- Differences awaiting product-owner sign-off: [BELLABOT_PREINSTALLATION_MAPPING.md §4](BELLABOT_PREINSTALLATION_MAPPING.md).
