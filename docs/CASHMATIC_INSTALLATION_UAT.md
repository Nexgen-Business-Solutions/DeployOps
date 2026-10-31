# Cashmatic On-site Installation — UAT scenarios (#23)

Hand-run scenarios for accepting the on-site checklist on the test site (`deployops.local`). Each one matches a requirement of #23 and an automated test in `deployops/tests/test_cashmatic_installation.py`. Use test data only: no real customers, and never real passwords or codes.

**Before you start:** a submitted Delivery Note with **two** Cashmatic serials; an Installation job from it, assigned to the test technician, moved to **On Site** (Supervisor: Start; Technician: Arrived on Site); the reference PDFs listed in **DeployOps Reference Files** for this checklist (see `deployops/reference_files/README.md`).

Record each result as Pass / Fail with the date, the tester and, for a Fail, what happened.

| # | Requirement | Steps | Expected | Automated test |
|---|---|---|---|---|
| U1 | Delivery-driven machines | Open the job | One row per delivered serial, each with its own status | `test_two_machines_on_one_delivery_have_separate_outcomes` |
| U2 | Documents | As the technician, open `/deployops` → Cashmatic Installation → the job → machine 1 → Start → Start checklist | Before **Arrived on Site**, there's no Start checklist. After it, "Documents for this checklist" lists the CDIG, Web panel, My Cashmatic App and Warnings files, each also shown under its section. **Read** opens the viewer | `test_every_embedded_document_is_listed_in_a_real_section` |
| U3 | Positioning, power, network | Look at sections 1 and 2 | 8 and 5 steps; Type of network and IP address, once each | `test_every_source_step_is_in_its_section_with_the_right_rule` |
| U4 | Every required step counts | Tick everything except one required step, fill the rest, Submit | Refused; the unticked step is marked | `test_each_unticked_required_step_stops_the_submit` |
| U5 | Training lists | Untick everything under Firsthand training, Submit | Refused: "tick at least one". The same applies to Web panel, Problem solving and Warnings | `test_each_group_needs_at_least_one_tick` |
| U6 | First refill and cashbox | Look at *Preparing the machine* | 4 steps; CashBOX may be left empty | `test_cashbox_and_remarks_are_optional_as_in_the_source` |
| U7 | POS integration | Choose Yes, leave brand empty, Submit; then choose No | Yes: brand and connector appear and are required. No: they disappear | `test_pos_details_are_required_only_with_pos_integration` |
| U8 | Photos | Submit with 2 photos, then add a third. Open a photo URL in a private window | Refused with 2; accepted with 3. Signed out, the photo is refused | `test_at_least_three_installation_photos`, `test_installation_photos_must_be_private_files_of_this_form` |
| U9 | Key handover | Leave the keys receiver's name or signature empty, Submit | Refused | `test_details_keys_and_sign_off_are_required` |
| U10 | No credentials | Type `password: test123` in Remarks | Refused with "do not enter passwords, PINs, OTPs or pairing codes" | `test_no_credentials_in_text` |
| U11 | Signatures | Submit without the client signature; then add the client and technician signatures, Submit | Refused without the client signature. Then submitted and locked; the signature record shows each signer, the time and the user. As a supervisor, the Desk job page lists the form under **Connections → Checklists** | `test_each_machine_needs_its_own_customer_signature`, `test_submit_locks_the_form_with_signers_and_snapshot`, `test_the_job_lists_its_checklists_in_desk_for_those_who_may_read_them` |
| U12 | Machine-level acceptance | Machine 1: Start Machine, then Complete Machine before and after submitting its checklist. Machine 2: Block Machine with a reason; try Submit for Review | Complete is refused until the checklist is submitted. Machine 1 is Completed and machine 2 Blocked, so the job can't go to review | `test_a_machine_completes_only_once_its_checklist_is_submitted`, `test_two_machines_on_one_delivery_have_separate_outcomes` |
| U13 | Who can see it | Open the checklist URL as another technician and as a guest | Refused for both; the supervisor and manager in scope can open it | `test_only_people_on_the_job_can_read_the_form` |
| U14 | Report | On the submitted checklist, tap **Report (PDF)**, then **Customer copy (PDF)**. In Desk, Print with **Cashmatic Installation Report** | Both open with every section, photos and signatures. Only the internal report has the job, form version and audit trail | `TestReport` |
| U15 | Phone | Repeat U2, U4 and U11 on a phone-sized window | Usable without horizontal scrolling | manual only |

## Not covered yet (open)
- Field mapping differences awaiting product-owner decisions: [CASHMATIC_INSTALLATION_MAPPING.md §4](CASHMATIC_INSTALLATION_MAPPING.md).
