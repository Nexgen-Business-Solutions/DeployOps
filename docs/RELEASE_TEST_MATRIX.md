# DeployOps — Release Test Matrix (#44, part of #30)

What must be proven before a release, and where each part is proven. **Automated** means it runs in CI on every pull request (`bench run-tests --app deployops`, plus the Frontend job). **Manual** means a Kiwi test case, run on the test site (`deployops.local`) and recorded before release. Kiwi cases live in `kiwi_tests/`, which is kept locally and not committed.

Status: ✅ covered · 🟡 partly covered (see notes) · ❌ not covered yet.

## 1. Whole flows (`deployops/tests/test_release_scenarios.py`)

These walk a real job from its ERPNext source to approval through the public APIs and the workflow, so a break anywhere in the chain fails here.

| Scenario | Automated | Manual | Status |
|---|---|---|---|
| **Sale:** order → preparation (serial picked, reserved) → pre-installation checklist → approved → delivery (reservation becomes Delivered) → installation on site → checklist with signatures → approved; both checklists locked with snapshots | `TestSale` | 16, 21, 26, 29, 32, 34 | ✅ |
| **Rental:** reserve for a subscription → installation job → approved (machine Deployed) → return → machine can be rented again | `TestRental` | 24, 25 | ✅ |
| **Two machines, partial outcome:** one installed, one blocked on site (no-go), the job can't be submitted while blocked, the blocked machine is cancelled with a reason, the job is approved, and the cancelled machine's serial is free for a later job | `TestTwoMachines` | 21, 22 | ✅ |
| **Serial conflicts:** a machine promised to an order can't be rented or put on a second order's preparation | `TestSerialConflicts` | 25, 26 | ✅ |
| **Maintenance:** Maintenance Visit → job straight on site → maintenance checklist with its fixed task rows → approved | `TestMaintenance` | 33 | ✅ |
| **Permissions across the flow:** the job, its checklist and its photo open for the assigned technician, Supervisor and Manager in scope; another technician and Guest are refused | `TestPermissionsAcrossTheFlow` | 20, 29 | ✅ |

## 2. Areas in detail

| Area (#44 / #30) | Automated tests | Manual | Status |
|---|---|---|---|
| **Sales sources:** usable orders and deliveries, snapshot, company boundary, Company user permissions | `test_erpnext_sources.py`, `test_job.py` (sources, pickers) | 11–16 | ✅ |
| **Delivery handoff:** one row per serial, later deliveries join the open job, returns and cancellations flagged, a Delivery Note never fails because of DeployOps | `test_delivery_handoff.py` | 34 | ✅ |
| **Serials per source:** a delivery's own serials, an order's delivered serials before stock, a subscription's allocated machines | `test_order_serials.py`, `test_job.py` | 14, 15 | ✅ |
| **Subscriptions / rental allocation:** reserve, deploy on approval, return, swap, one active allocation per machine (enforced by the database) | `test_allocations.py` | 24–27 | ✅ |
| **Serial history** | `test_allocations.py` (`test_history_*`) | 27 | ✅ |
| **Maintenance (Visit / Schedule)** | `test_erpnext_sources.py`, `test_job_workflow.py` (`test_maintenance_goes_straight_on_site`), `TestMaintenance` | 33 | 🟡 Maintenance **Schedule** is only covered as a source, not as a whole flow; #17 is still open |
| **Roles and permission matrix** | `test_permission_matrix.py`, `test_matrix_unit.py`, `test_security_negative.py` (over HTTP) | 01–04 | ✅ |
| **Equipment profiles and job visibility** (lists, reports, link search, direct URL, print, attachments; revoked access; System Manager) | `test_equipment_access.py`, `test_job_visibility.py` | 06–10, 20 | ✅ |
| **Workflow:** paths, who may do what, reasons, block/unblock, return for correction, cancel, locks | `test_job_workflow.py` | 21–23 | ✅ |
| **No-go / blocked jobs** | `test_job_workflow.py` (`test_submit_needs_every_machine_done_and_none_blocked`), `TestTwoMachines` | 22 | 🟡 Blocking is manual (Block Machine). Whether a **NO GO** or **FAIL** answer should block automatically is a product-owner decision (open) |
| **Checklists:** five forms, required answers, conditions, versions and snapshots, serial before submit, locking, cancel by Manager | `test_checklists.py`, `test_technician_api.py` | 28–33 | 🟡 Field mapping awaits product-owner sign-off (#40) |
| **Digital signatures:** drawn signature plus a server-recorded signer, time and capturing user; signer name required | `test_checklists.py` (`test_signatures_*`, `test_a_signature_needs_the_signer_name`) | 29, 32 | ✅ |
| **Evidence files:** private, attached to the form, visible only with the job; foreign or public files refused | `test_checklists.py`, `test_job_visibility.py`, `TestPermissionsAcrossTheFlow` | 20, 29 | ✅ |
| **Reference manuals (PDF) in checklists:** private, readable by DeployOps roles only, shown per section | `test_reference_files.py`, `src/lib/pdf.test.ts` | — | ✅ (in-app viewer checked by hand, see §4) |
| **No secrets in checklists:** passwords, PINs, OTPs and pairing codes refused in text and table cells | `test_checklists.py` (`test_secrets_*`) | 32 | ✅ |
| **Technician app (React):** session, guest shell, URLs under `/deployops`, API per screen | `test_technician_api.py`, `test_install.py`, `test_security_negative.py`, frontend unit tests | 02, 05, 31–33 | 🟡 No automated browser tests in CI; browser runs are manual (§4) |
| **Printable reports / PDF output** (#27) | — | — | ❌ Not built yet |
| **Production rollout approval** | — | §5 below | 🟡 A release step, not code |

## 3. Known gaps to close before a production release
1. **Printable reports (#27)** don't exist yet, so "PDF" in #44 can't be tested.
2. **Automatic no-go:** whether a NO GO or FAIL answer blocks a machine, and whether completion needs a submitted checklist, are open product-owner decisions.
3. **Return for Correction:** which machines reopen is undefined (open with the product owner).
4. **Field mapping sign-off (#40)** for all five checklists.
5. **Maintenance Schedule** as a whole flow (#17).
6. **Job audit integrity fixes** (`task/39-job-audit-integrity`) are pushed but not merged; until they are, status-log rows can be rewritten and serials changed under a submitted checklist.
7. **Browser end-to-end tests** run by hand only. Adding them to CI needs a new dev dependency (e.g. Playwright); that's not agreed.

## 4. Manual browser run (each release)
On `deployops.local`, as tech@test.local on a phone-sized window, then on a desktop:
1. Sign in at `/deployops`; the home screen shows the five checklists with job counts.
2. Open a job, start a machine, start its checklist; the reference documents block and section cards show; **Read** opens the viewer and pages turn.
3. Fill the checklist, add three photos and the signatures; reload: everything is kept.
4. Submit: missing answers are marked; with no serial on the job, the warning shows and Submit doesn't proceed.
5. Submit for real: the form is locked, with "Submitted on … by …".
6. As a guest, the photo and reference file URLs are refused.

## 5. Production rollout approval
Before deploying to production, the release owner records:
1. The CI run for the release commit: **Server**, **Frontend** and **Frappe Linter** all green.
2. The Kiwi run (cases above) with results, and the manual browser run (§4).
3. The open gaps from §3 that the product owner accepts for this release.
4. A backup of the production site taken before `bench migrate`, and the rollback plan: restore that backup and reinstall the previous app version.
5. The product owner's written approval.

## How to run
```bash
# backend (on the test site)
bench --site deployops.local run-tests --app deployops
bench --site deployops.local run-tests --module deployops.tests.test_release_scenarios
# frontend
cd apps/deployops/frontend && yarn typecheck && yarn lint && yarn test
```
