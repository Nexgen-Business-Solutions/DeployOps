# DeployOps — Compatibility Report & Deployment Approach (#8 / #33)

**Status:** DRAFT FOR PRODUCT-OWNER APPROVAL. Feature implementation (#9 onward) stays blocked until this report is accepted and the open questions in §6 are answered.
**Prepared:** 2026-10-17 by @Nexgen-Kimbi (AI-assisted).
**Scope:** Feature [#8](https://github.com/Nexgen-Business-Solutions/DeployOps/issues/8), task [#33](https://github.com/Nexgen-Business-Solutions/DeployOps/issues/33).

Every statement below is labelled:
- **CONFIRMED**: verified by inspecting the local bench, the ERPNext source or GitHub on the date above.
- **PROPOSAL**: recommended approach, not yet approved.
- **OPEN**: not verifiable from the development environment; needs the owner or Frappe Cloud dashboard access.

---

## 1. Environments

### 1.1 Local development bench (CONFIRMED)
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
| wkhtmltopdf | **not installed** (see risk R7) |
| Site | `deployops.local` (default site), apps: `frappe`, `erpnext` |
| System settings | Time zone `Africa/Douala`, country Cameroon, date format `dd-mm-yyyy`, 2FA off |
| Companies | One: `Massarie` (Cameroon, XAF) |

**The local site is an empty development site** (CONFIRMED). It has 0 Customers, Items, Serial Nos, Sales Orders, Delivery Notes, Subscriptions and Maintenance Visits/Schedules, and 3 users. It has **no `Cashmatic Installation` DocType**, no custom DocTypes or modules, and only 3 framework Custom Fields (`impersonate` on DocShare/DocPerm/Custom DocPerm). So:
- the local site **cannot** be used to verify production configuration, data volumes, customisations or the legacy DocType;
- all tests must create their own anonymised fixtures. Real customer data must never be copied into the repository (AGENTS.md).

### 1.2 Repository and GitHub (CONFIRMED)
- `Nexgen-Business-Solutions/DeployOps` is private, default branch `main`. The local git remote is named `upstream`, not `origin`.
- The repository currently contains **documentation only**. It is not yet an installable Frappe app (no `pyproject.toml`, `hooks.py` or modules) and is not listed in `sites/apps.txt`. Creating the app is #9 / #34.
- No GitHub Actions workflows exist. **`main` has no branch protection.**
- Issues #1–#44 exist. #35–#44 match the developer guide. #28 and #29 are closed duplicates of #26 and #27.
- The local `gh` token lacks the `read:project` / `project` scopes, so Project #39 board columns cannot be read or moved from the CLI. Fix: `gh auth refresh -s read:project,project`.

### 1.3 Frappe Cloud production / staging (OPEN)
None of the following can be observed from the development environment:
- the production site's Frappe/ERPNext versions, and whether it is on `version-16` or still on v15;
- the Frappe Cloud plan, and whether the site is on a **shared** bench or a **private bench group**;
- whether a staging site exists;
- installed apps, custom fields, Customize Form changes, Workflows and Print Formats;
- whether the `Cashmatic Installation` DocType exists, how many records it has, and its dependencies;
- multi-company setup, users and roles, backup schedule and retention.

## 2. ERPNext v16 schema findings relevant to the architecture (CONFIRMED from installed source)

| Area | Finding | Impact |
|---|---|---|
| Serials on Delivery Note | `Delivery Note Item` carries `serial_and_batch_bundle` (Link → **Serial and Batch Bundle**), `use_serial_batch_fields` and a legacy `serial_no` Text field. Local Stock Settings: `use_serial_batch_fields = 1`, auto-create outward bundle = 1. | #16 / #43 must read dispatched serials from the **Serial and Batch Bundle entries** (falling back to `serial_no` text only when no bundle exists). It must not parse free text as the primary source. The production Stock Settings value must be confirmed (OPEN). |
| Serial No | Has `item_code`, `status`, `warehouse`, `customer`, `company`, `asset`, `warranty_expiry_date`, `amc_expiry_date`, `maintenance_status`, `reference_doctype/name`. These are maintained by the stock ledger. | DeployOps should **read** Serial No and keep allocation/deployment history in its own records (#14). It should not write `status`, `warehouse` or `customer`, so stock semantics stay intact. |
| Subscription | Links `party_type/party`, `company`, `plans`. It has **no item or serial field**. | This confirms the spec: a rental device cannot be derived from a Subscription. #14 / #15 need an explicit Subscription → Serial No allocation record. |
| Maintenance Visit | Child `Maintenance Visit Purpose` has `item_code`, `serial_no`, `service_person`, `work_done`, `prevdoc_doctype/docname`, `maintenance_schedule_detail`. | #17 can link a DeployOps maintenance checklist per Visit Purpose line (serial-level) without duplicating visits. |
| Installation Note | DocType exists (0 records locally). | ARCHITECTURE §7 decision: whether sold-device installs also create or link an Installation Note. Not for rentals. |
| Workflow | Native Frappe `Workflow` is available. | #19 can choose between a native Workflow (configurable transitions and roles) and controller-enforced states. Proposal in §4.4. |
| Asset | DocType exists. | Not needed for V1 (ARCHITECTURE §7). |
| PDF generation | Frappe v16 `Print Format` has a `pdf_generator` field (wkhtmltopdf or Chrome-based generator). | #27 report rendering depends on which generator production uses (OPEN, R7). |

## 3. Compatibility conclusion

**PROPOSAL:** DeployOps targets **Frappe v16 / ERPNext v16 only**.
- The app's `pyproject.toml` should declare `requires-python = ">=3.14,<3.15"` and `[tool.bench.frappe-dependencies] frappe = ">=16.50.0,<17.0.0"`, matching ERPNext v16.
- **Condition:** production must be on v16. If production is v15, there are two options: (a) upgrade production to v16 first, as a separate owner-approved project, or (b) target v15, which needs Python 3.10/3.11 and a different dependency floor and changes the CI matrix. This is decision **Q1**. No app code should be written before it is answered.

## 4. Install / deployment approach (PROPOSAL)

### 4.1 Pipeline
```
local bench (deployops.local)
   → feature branch + PR (feature/<issue>-<slug>)
   → GitHub Actions CI: fresh bench with frappe+erpnext version-16, install DeployOps, run tests
   → review + merge to main
   → Frappe Cloud STAGING site: deploy, `bench migrate`, UAT with anonymised data
   → owner approval
   → Frappe Cloud PRODUCTION: take a backup, then deploy the same commit
```

### 4.2 Frappe Cloud prerequisites (to verify, Q2–Q4)
- Frappe Cloud only installs custom apps on a **private bench group**, not on shared benches. If production is on a shared bench, a plan or bench change is required.
- The private GitHub repo is connected through the Frappe Cloud GitHub App. Someone with org-admin rights on both sides must authorise it.
- A **staging site** on the same bench group, or a separate bench group pinned to the same Frappe/ERPNext versions, for UAT before production.
- Whoever deploys needs Frappe Cloud team permission to deploy the bench and update sites, but not to drop sites.

### 4.3 Schema and data change rules
- All DocTypes are defined as JSON in the app module, so they are version controlled. **No Customize Form or "custom" DocTypes in production.**
- Fields added to ERPNext DocTypes (e.g. a link from Delivery Note to a DeployOps Job) are created by code (`create_custom_fields` in `after_install` plus a patch), tagged with the DeployOps module. ERPNext core is never edited.
- Data changes go through idempotent patches in `patches.txt`. Each patch is tested on a fresh site and on a staging copy before production.
- No fixture may contain customer data, credentials or employee personal data.

### 4.4 Workflow engine for #19 (initial recommendation, decided in #19)
Use controller-enforced states with an explicit transition table and server-side checks (`validate` / `before_submit`). Optionally mirror them in a native Workflow for UI buttons. Reason: the job has per-device states, NO GO blocks and override rules that a plain Workflow cannot express on its own.

### 4.5 Rollback
1. Before every production deploy, take an on-demand **Frappe Cloud backup** (database plus files) and record its timestamp in the PR or release notes.
2. Code rollback: redeploy the previous app commit on the bench group.
3. Data rollback: every patch documents whether it is reversible. Irreversible patches need an explicit owner sign-off and a fresh backup.
4. **Do not** use `bench remove-app` / uninstall as a rollback. It drops DeployOps DocTypes and their data.
5. Last resort: restore the site from the pre-deploy backup. This loses all writes made after the deploy, so it needs owner approval.

### 4.6 Repository hygiene (needs repo admin to apply)
- Enable branch protection on `main`: PR required, 1 approving review, CI must pass, no force-push.
- Add GitHub Actions CI in #34.

## 5. Risks

| # | Risk | Likelihood / impact | Mitigation |
|---|---|---|---|
| R1 | Production is not on Frappe/ERPNext v16 | Unknown / High | Q1 before #9; pin versions in `pyproject.toml` and CI |
| R2 | Production is on a shared Frappe Cloud bench, so custom apps cannot be installed | Unknown / High | Q2; plan or bench change approved by owner |
| R3 | No staging site, so the first install would be on production | Unknown / High | Q3; create staging before #9 is deployed anywhere |
| R4 | The local dev site has no data and no legacy DocType, so production customisations and the `Cashmatic Installation` dependencies are invisible | Confirmed / Medium | Q5: read-only export of customisation metadata (DocType/Custom Field/Property Setter JSON, **no records**) from production for #31 and #13 |
| R5 | Serial handling differs (Serial and Batch Bundle vs legacy text), depending on production Stock Settings | Medium / High | Q6; #43 tests cover both modes |
| R6 | `main` unprotected, no CI | Confirmed / Medium | §4.6 |
| R7 | PDF generator: wkhtmltopdf missing locally, and production generator unknown | Confirmed locally / Medium | Install wkhtmltopdf 0.12.6 (patched Qt) locally or choose the Chrome generator; confirm production setting (Q7) before #27 |
| R8 | Sensitive data: the sample PDF contains credentials and PII, and `docs/CHECKLIST_SPECS.md` line 3 names the sample customer/site | Confirmed / Medium | Owner decides whether to anonymise that line (Q9); never use the sample in fixtures |
| R9 | Multi-company: local has one company, production may have more | Unknown / Medium | Q8; permission tests (#12, #35) include a second company |
| R10 | Board automation: `gh` token lacks project scope | Confirmed / Low | `gh auth refresh -s read:project,project` |

## 6. Open questions for the product owner

| # | Question | Blocks |
|---|---|---|
| Q1 | What exact Frappe and ERPNext versions does **production** run? Is it on `version-16`? | #9 (app target) |
| Q2 | Frappe Cloud plan: is the production site on a private bench group, and can we connect the private `DeployOps` GitHub repo to it? Who holds Frappe Cloud team admin? | #9 deploy, #32 |
| Q3 | Does a staging site exist? If not, may we create one (cost and plan), and from what data: fresh, or an anonymised copy? | #9, all UAT |
| Q4 | Who is authorised to deploy to staging, and who approves production deploys? | #32 |
| Q5 | May we export read-only **metadata** (no records) from production: Custom Fields, Property Setters, Workflows, Print Formats and the `Cashmatic Installation` DocType definition with record count? | #13, #31 |
| Q6 | Production Stock Settings: `use_serial_batch_fields` and auto-bundle creation. Are serialised Items (Cashmatic, BellaBot) already set up with `has_serial_no`? | #14, #16, #43 |
| Q7 | Which PDF generator does production use (wkhtmltopdf or Chrome)? | #27 |
| Q8 | How many companies are in production, and should DeployOps jobs be company-scoped? | #10–#12 |
| Q9 | Should the customer/site name in `docs/CHECKLIST_SPECS.md` (line 3) be anonymised? | Hygiene |
| Q10 | Backup policy: are Frappe Cloud automated backups enabled for production, and what is the retention? Is an offsite copy required? | §4.5 |

## 7. Manual verification performed (evidence for #33)
1. `git -C apps/{frappe,erpnext} describe --tags`: `v16.52.0`, `v16.51.1`.
2. Read-only Python inspection of `deployops.local` (`frappe.connect()`; only `get_meta`, `count`, `get_all`; no writes). It confirmed the versions, system settings, companies, DocType existence, record counts and the field lists in §2.
3. `apps/frappe/pyproject.toml` / `package.json`: Python `>=3.14,<3.15`, Node `>=24`. `apps/erpnext/pyproject.toml`: `frappe >=16.50.0,<17.0.0`.
4. `gh repo view`, branch-protection API and Actions API: private repo, `main` unprotected, 0 workflows.

No production system was accessed or changed.

## 8. Next step after approval
Start #9 / #34. Create the installable app skeleton in this repo (`pyproject.toml`, `hooks.py`, a `DeployOps` module, an empty workspace, the test bootstrap and a GitHub Actions CI on v16), install it on `deployops.local` only, and open a PR. No DocTypes for business objects until #18 / #20 are planned and approved.
