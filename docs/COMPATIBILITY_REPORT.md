# DeployOps — Compatibility Report & Development Approach (#8 / #33)

**Status:** DRAFT FOR PRODUCT-OWNER APPROVAL. Feature implementation (#9 onward) stays blocked until this report is accepted.
**Prepared:** 2026-10-17 by @Nexgen-Kimbi (AI-assisted). **Revised:** 2026-10-17 after an owner decision on environment scope.
**Scope:** Feature [#8](https://github.com/Nexgen-Business-Solutions/DeployOps/issues/8), task [#33](https://github.com/Nexgen-Business-Solutions/DeployOps/issues/33).

Every statement below is labelled:
- **DECIDED**: confirmed by the owner.
- **CONFIRMED**: verified by inspecting the local bench, the ERPNext source or GitHub on the date above.
- **PROPOSAL**: recommended approach, not yet approved.

---

## 0. Owner decisions (DECIDED, 2026-10-17)
1. **Target platform: Frappe v16 / ERPNext v16**, matching the local bench.
2. **Local development only.** The team will not get access to Frappe Cloud, a VPS or any production or hosted staging system. All development, testing and UAT happen on the local bench.

As a result, this project **does not deploy anything**. All work is delivered as a version-controlled, installable Frappe app in this GitHub repository.

## 1. Environments

### 1.1 Local development bench (CONFIRMED). The only environment
| Component | Value |
|---|---|
| Host | WSL2, Ubuntu 24.04.4 LTS, 8 vCPU, 15 GiB RAM |
| Bench path | `~/frappe/massarie_project` (bench CLI 5.31.0) |
| Frappe | **16.52.0** (`version-16`) |
| ERPNext | **16.51.1** (`version-16`, commit `5af6561f`) |
| Python | 3.14.6 (Frappe v16 requires `>=3.14,<3.15`) |
| Node / Yarn | 24.18.0 / 1.22.22 (Frappe v16 requires Node `>=24`) |
| MariaDB | 10.11.14 |
| Redis | 7.0.15 |
| wkhtmltopdf | **not installed** (see risk R4) |
| Site | `deployops.local` (default site), apps: `frappe`, `erpnext` |
| System settings | Time zone `Africa/Douala`, country Cameroon, date format `dd-mm-yyyy`, 2FA off |
| Companies | One: `Massarie` (Cameroon, XAF) |

**The local site is an empty development site** (CONFIRMED). It has 0 Customers, Items, Serial Nos, Sales Orders, Delivery Notes, Subscriptions and Maintenance Visits/Schedules, and 3 users. It has **no `Cashmatic Installation` DocType**, no custom DocTypes or modules, and only 3 framework Custom Fields (`impersonate` on DocShare/DocPerm/Custom DocPerm). So:
- all tests and UAT must create their own **anonymised** master data (Company, Items with serials, Customers, Sales Orders, Delivery Notes, Subscriptions, Maintenance Visits);
- real customer data, credentials or employee personal data must never be copied into the repository or into fixtures (AGENTS.md).

### 1.2 Local sites (PROPOSAL)
| Site | Purpose |
|---|---|
| `deployops.local` | Day-to-day development and manual demos. |
| `deployops-test.local` | Automated tests (`allow_tests: true`). Rebuilt from scratch whenever needed, so test runs never touch the development data. |
| `deployops-uat.local` | Stands in for staging. A clean v16 site where the app is installed fresh from a tagged commit, `bench migrate` is run, and the UAT scenarios (FUNCTIONAL_SPEC §8) are demonstrated with anonymised demo data. |

### 1.3 Repository and GitHub (CONFIRMED)
- `Nexgen-Business-Solutions/DeployOps` is private, default branch `main`. The local git remote is named `upstream`, not `origin`.
- The repository currently contains **documentation only**. It is not yet an installable Frappe app (no `pyproject.toml`, `hooks.py` or modules) and is not listed in `sites/apps.txt`. Creating the app is #9 / #34.
- No GitHub Actions workflows exist. **`main` has no branch protection.**
- Issues #1–#44 exist. #35–#44 match the developer guide. #28 and #29 are closed duplicates of #26 and #27.
- The local `gh` token lacks the `read:project` / `project` scopes, so Project #39 board columns cannot be read or moved from the CLI. Fix: `gh auth refresh -s read:project,project`.

### 1.4 Hosted / production environments: out of scope (DECIDED)
There is no access to Frappe Cloud, a VPS or the production site. So the following **cannot be verified** by this team:
- production versions;
- production customisations (Custom Fields, Property Setters, Workflows, Print Formats);
- whether the experimental `Cashmatic Installation` DocType exists, with what records and dependencies;
- production Stock Settings, companies and users.

Section 5 (risks) covers the effect of this.

## 2. ERPNext v16 schema findings relevant to the architecture (CONFIRMED from installed source)

| Area | Finding | Impact |
|---|---|---|
| Serials on Delivery Note | `Delivery Note Item` carries `serial_and_batch_bundle` (Link → **Serial and Batch Bundle**), `use_serial_batch_fields` and a legacy `serial_no` Text field. Local Stock Settings: `use_serial_batch_fields = 1`, auto-create outward bundle = 1. | #16 / #43 must read dispatched serials from the **Serial and Batch Bundle entries** (falling back to `serial_no` text only when no bundle exists). It must not parse free text as the primary source. Tests cover both settings. |
| Serial No | Has `item_code`, `status`, `warehouse`, `customer`, `company`, `asset`, `warranty_expiry_date`, `amc_expiry_date`, `maintenance_status`, `reference_doctype/name`. These are maintained by the stock ledger. | DeployOps should **read** Serial No and keep allocation/deployment history in its own records (#14). It should not write `status`, `warehouse` or `customer`, so stock semantics stay intact. |
| Subscription | Links `party_type/party`, `company`, `plans`. It has **no item or serial field**. | This confirms the spec: a rental device cannot be derived from a Subscription. #14 / #15 need an explicit Subscription → Serial No allocation record. |
| Maintenance Visit | Child `Maintenance Visit Purpose` has `item_code`, `serial_no`, `service_person`, `work_done`, `prevdoc_doctype/docname`, `maintenance_schedule_detail`. | #17 can link a DeployOps maintenance checklist per Visit Purpose line (serial-level) without duplicating visits. |
| Installation Note | DocType exists (0 records locally). | ARCHITECTURE §7 decision: whether sold-device installs also create or link an Installation Note. Not for rentals. |
| Workflow | Native Frappe `Workflow` is available. | #19 can choose between a native Workflow (configurable transitions and roles) and controller-enforced states. Proposal in §4.4. |
| Asset | DocType exists. | Not needed for V1 (ARCHITECTURE §7). |
| PDF generation | Frappe v16 `Print Format` has a `pdf_generator` field (wkhtmltopdf or Chrome-based generator). | #27 needs one generator installed locally (R4). |

## 3. Compatibility conclusion (DECIDED)
DeployOps targets **Frappe v16 / ERPNext v16 only**:
- `pyproject.toml`: `requires-python = ">=3.14,<3.15"`;
- `[tool.bench.frappe-dependencies] frappe = ">=16.50.0,<17.0.0"`, matching ERPNext v16;
- ERPNext declared as a required app (`required_apps = ["erpnext"]` in `hooks.py`);
- CI runs against `version-16` of both apps.

The local bench already satisfies all of these.

## 4. Development approach (PROPOSAL)

### 4.1 Pipeline (local only)
**DECIDED:** nothing is pushed to GitHub until all the work is complete. Branches, commits and reviews stay on the local machine until then.
```
deployops.local (develop)
   → local feature branch (feature/<issue>-<slug>), small commits
   → tests on deployops-test.local (bench run-tests --app deployops)
   → owner review of the local branch (diff + test output)
   → merge into local main
   → fresh install / migrate on deployops-uat.local and run the UAT scenarios
   → owner acceptance
   → (once everything is complete) push to GitHub
```

### 4.2 Tests and CI
- During development, tests run only on the local bench. Each feature's test output is recorded with its merge, as evidence.
- A GitHub Actions workflow is written in #34 so CI is ready when the code is pushed. Each run sets up MariaDB and Redis services, a fresh `version-16` bench with ERPNext, installs DeployOps on a throwaway site and runs `bench run-tests --app deployops`. It only starts running after the push.

### 4.3 Schema and data change rules
- All DocTypes are defined as JSON in the app module, so they are version controlled. **No Customize Form or "custom" DocTypes created through the UI.**
- Fields added to ERPNext DocTypes (e.g. a link from Delivery Note to a DeployOps Job) are created by code (`create_custom_fields` in `after_install` plus a patch), tagged with the DeployOps module. ERPNext core is never edited.
- Data changes go through idempotent patches in `patches.txt`. Each patch is tested on a fresh site (`deployops-test.local`) **and** as an upgrade on `deployops-uat.local` carrying data from the previous version.
- No fixture may contain customer data, credentials or employee personal data.

### 4.4 Workflow engine for #19 (initial recommendation, decided in #19)
Use controller-enforced states with an explicit transition table and server-side checks (`validate` / `before_submit`). Optionally mirror them in a native Workflow for UI buttons. Reason: the job has per-device states, NO GO blocks and override rules that a plain Workflow cannot express on its own.

### 4.5 Backup and rollback (local)
1. Before any `bench migrate` that runs a new patch on `deployops.local` or `deployops-uat.local`, run `bench --site <site> backup --with-files`. Backups stay under `sites/<site>/private/backups/` and are **never committed**.
2. Code rollback: check out the previous commit or tag and run `bench migrate`.
3. Data rollback: restore the site from the pre-migrate backup (`bench --site <site> restore ...`). Every patch documents whether it is reversible.
4. **Do not** use `bench remove-app` / uninstall as a rollback. It drops DeployOps DocTypes and their data.

### 4.6 Repository hygiene (needs repo admin to apply)
- Enable branch protection on `main`: PR required, 1 approving review, CI must pass, no force-push.
- Add GitHub Actions CI in #34.

## 5. Risks

| # | Risk | Likelihood / impact | Mitigation |
|---|---|---|---|
| R1 | The legacy `Cashmatic Installation` DocType is not on the local site, so #31 (retirement audit) cannot be done locally | Confirmed / Medium | DeployOps must never depend on it. #31 is reduced to a written retirement procedure, or deferred |
| R2 | All test data is synthetic. Real-world serial, Delivery Note and Subscription patterns may differ from what we assume | Confirmed / Medium | Build fixtures from the FUNCTIONAL_SPEC §8 scenarios |
| R3 | `main` unprotected, no CI | Confirmed / Medium | §4.6 |
| R4 | wkhtmltopdf is not installed locally, so PDF reports (#27) cannot be rendered yet | Confirmed / Medium | Install wkhtmltopdf 0.12.6 (patched Qt) or use the v16 Chrome generator; decide in #27 |
| R5 | Sensitive data: the sample PDF contains credentials and PII, and `docs/CHECKLIST_SPECS.md` line 3 names the sample customer/site | Confirmed / Medium | Never use the sample in fixtures; anonymise that line before the push |
| R6 | Multi-company: local has one company | Unknown / Medium | Permission tests (#12, #35) create a second company regardless |
| R7 | Board automation: `gh` token lacks project scope | Confirmed / Low | `gh auth refresh -s read:project,project` |
| R8 | One local machine. Disk failure or WSL reset loses unpushed work and local sites | Low / Medium | Regular off-machine copy of the repo (`git bundle create` to another disk); sites can be rebuilt from the repo and fixtures |

## 6. Manual verification performed (evidence for #33)
1. `git -C apps/{frappe,erpnext} describe --tags`: `v16.52.0`, `v16.51.1`.
2. Read-only Python inspection of `deployops.local` (`frappe.connect()`; only `get_meta`, `count`, `get_all`; no writes). It confirmed the versions, system settings, companies, DocType existence, record counts and the field lists in §2.
3. `apps/frappe/pyproject.toml` / `package.json`: Python `>=3.14,<3.15`, Node `>=24`. `apps/erpnext/pyproject.toml`: `frappe >=16.50.0,<17.0.0`.
4. `gh repo view`, branch-protection API and Actions API: private repo, `main` unprotected, 0 workflows.

No hosted or production system was accessed. None is in scope.

## 7. Next step after approval
Start #9 / #34. Create the installable app skeleton in this repo (`pyproject.toml`, `hooks.py`, a `DeployOps` module, an empty workspace, the test bootstrap and a GitHub Actions CI on v16), create `deployops-test.local`, install the app on the local sites only, and commit on a local branch for review (no push). No DocTypes for business objects until #18 / #20 are planned and approved.
