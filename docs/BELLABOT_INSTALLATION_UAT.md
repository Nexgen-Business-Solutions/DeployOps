# BellaBot On-site Installation — UAT scenarios (#25)

Hand-run scenarios for accepting the checklist on the test site. Each one matches a requirement of #25 and an automated test in `deployops/tests/test_bellabot_installation.py`. Use test data only: no real customers, and never real passwords or codes.

**Before you start:** a Delivery Note with **two** BellaBot machines; an Installation job from it, assigned to the test technician, started by a Supervisor, with the technician arrived on site; the reference files listed in **DeployOps Reference Files** for this checklist (see `deployops/reference_files/README.md`).

Record each result as Pass / Fail with the date, the tester and, for a Fail, what happened.

| # | Requirement | Steps | Expected | Automated test |
|---|---|---|---|---|
| U1 | Other answers | In Safety tests, tick nothing and fill **Other safety test**; then clear it and try Submit. Choose Deployment type = Other and leave its text empty | Other answers the group; a blank one doesn't. Deployment type needs its text | `TestOtherAnswers` |
| U2 | Documents | Open the checklist as the technician | The deployment manual is under Mapping, the operation guide under Enabled modes, and the maintenance and care image under Customer advisories, and they open in the viewer | `TestDocuments` |
| U3 | No credentials | Type `password: test123` in Setup notes, and in an Other box | Refused with "do not enter passwords, PINs, OTPs or pairing codes" | `test_no_credentials_in_text`, `test_no_credentials_in_an_other_answer` |
| U4 | Explanations | Set a mode test to Fail, then damage to Severe, with no notes; Submit | Refused each time until the note is filled in. Not Tested and Minor damage need none | `TestRequiredExplanations` |
| U5 | All good | Machine 1: submit with PASS and Handover = Yes, Start Machine, Complete Machine | Completed | `test_a_machine_completes_only_once_its_checklist_is_submitted` |
| U6 | Safety FAIL blocks | Submit with FAIL and details; try Submit for Review | The machine is Blocked, the Status Log shows the details, and the job is refused | `TestSafetyFail` |
| U7 | Handover No blocks | On a new job, submit with Handover = No and remarks; try Submit for Review | The same, with the remarks in the Status Log | `TestHandoverNo` |
| U8 | Clearing a block | As the technician, look for Unblock Machine. As a Supervisor, Unblock with no reason, then with one; Complete Machine as the technician | Technician can't. Supervisor is refused with no reason, then the machine goes to In Progress, the reason is logged, and it completes | `test_the_technician_cannot_clear_it`, `test_clearing_needs_a_reason_then_the_machine_can_complete` |
| U9 | Scope | As a Supervisor without BellaBot in their equipment profile, try to open the job | Refused | `test_an_out_of_scope_supervisor_cannot_clear_it` |
| U10 | Two machines | Machine 1 passes and machine 2 fails safety | Machine 2 is Blocked, machine 1 isn't, and the job can't go to review | `test_each_delivered_machine_has_its_own_form_and_outcome` |
| U11 | Reports | On a submitted checklist, open **Report (PDF)** and **Customer copy (PDF)**. In Desk, Print with **BellaBot Installation Report** | Both open with the answers, photos and signatures. The customer copy has no job reference or audit trail | `TestReport` |
| U12 | Rental | Reserve a machine on a Subscription, make an Installation job from it, and start the checklist | The form shows the reserved machine's serial | `test_a_rental_machine_from_a_subscription_gets_the_same_form` |

## Not covered yet (open)
- Differences awaiting product-owner sign-off: [BELLABOT_INSTALLATION_MAPPING.md §4](BELLABOT_INSTALLATION_MAPPING.md).
