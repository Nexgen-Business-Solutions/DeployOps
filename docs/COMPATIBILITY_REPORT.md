# DeployOps — Compatibility Report (#8 / #33)

**Status:** Draft for review. Feature implementation (#9 onward) starts only after this report is approved.
**Prepared:** 2026-10-17 by @Nexgen-Kimbi (AI-assisted).
**Scope:** Feature [#8](https://github.com/Nexgen-Business-Solutions/DeployOps/issues/8), task [#33](https://github.com/Nexgen-Business-Solutions/DeployOps/issues/33).

---

## 1. Versions

| Component | Version | Requirement source |
|---|---|---|
| Frappe | **16.52.0** (`version-16`) | Target version |
| ERPNext | **16.51.1** (`version-16`, commit `5af6561f`) | Target version; requires `frappe >=16.50.0,<17.0.0` |
| Python | 3.14.6 | Frappe v16 requires `>=3.14,<3.15` |
| Node / Yarn | 24.18.0 / 1.22.22 | Frappe v16 requires Node `>=24` |
| MariaDB | 10.11.14 | |
| Redis | 7.0.15 | |
| bench CLI | 5.31.0 | |
| wkhtmltopdf | not installed | Needed for PDF print formats unless the v16 Chrome PDF generator is used |

**Target:** DeployOps is built for **Frappe v16 / ERPNext v16 only**. The app will declare:
- `requires-python = ">=3.14,<3.15"`;
- `[tool.bench.frappe-dependencies] frappe = ">=16.50.0,<17.0.0"`;
- `required_apps = ["erpnext"]` in `hooks.py`.

The local bench already meets all of these.

## 2. Hosting restrictions
- Development is **local only**. There is no access to Frappe Cloud, a VPS or any production or hosted staging site.
- No code is committed or pushed until the owner has reviewed and approved it.
- Because nothing can be checked on a hosted site, everything in this report was verified on the local bench and in the installed Frappe/ERPNext source.

## 3. Available environments

### 3.1 Local bench
| Item | Value |
|---|---|
| Host | WSL2, Ubuntu 24.04.4 LTS, 8 vCPU, 15 GiB RAM |
| Bench path | `~/frappe/massarie_project` |
| Existing site | `deployops.local` (default site), apps: `frappe`, `erpnext` |
| System settings | Time zone `Africa/Douala`, country Cameroon, date format `dd-mm-yyyy`, 2FA off |
| Companies | One: `Massarie` (Cameroon, XAF) |
| Data | Empty development site: no Customers, Items, Serial Nos, Sales Orders, Delivery Notes, Subscriptions or Maintenance Visits/Schedules; 3 users |

### 3.2 Site
All development and testing uses the existing `deployops.local` site.

### 3.3 Repository
- `Nexgen-Business-Solutions/DeployOps`, private, default branch `main`. The local remote is named `upstream`.
- The repository contains documentation only. It is not yet an installable Frappe app (no `pyproject.toml`, `hooks.py` or modules) and is not in `sites/apps.txt`. Creating the app is #9 / #34.
- No CI workflows. `main` has no branch protection.

## 4. Compatibility findings (ERPNext v16 schema)

| Area | Finding | Impact on DeployOps |
|---|---|---|
| Serials on Delivery Note | `Delivery Note Item` has `serial_and_batch_bundle` (Link → Serial and Batch Bundle), `use_serial_batch_fields` and an older `serial_no` Text field. Local Stock Settings: `use_serial_batch_fields = 1`, auto-create outward bundle = 1. | Dispatched serials are read from the **Serial and Batch Bundle entries**, falling back to the `serial_no` text only when no bundle exists. Tests cover both settings. |
| Serial No | Has `item_code`, `status`, `warehouse`, `customer`, `company`, `warranty_expiry_date`, `amc_expiry_date`, `maintenance_status`, `reference_doctype/name`. These are maintained by the stock ledger. | DeployOps reads Serial No and keeps allocation and deployment history in its own records. It never writes `status`, `warehouse` or `customer`. |
| Subscription | Links `party_type/party`, `company`, `plans`; no item or serial field. | A rental device cannot be derived from a Subscription. An explicit Subscription → Serial No allocation record is needed (#14 / #15). |
| Maintenance Visit | Child `Maintenance Visit Purpose` has `item_code`, `serial_no`, `service_person`, `work_done`, `prevdoc_doctype/docname`, `maintenance_schedule_detail`. | Maintenance checklists can link per Visit Purpose line, at serial level, without duplicating visits (#17). |
| Installation Note | DocType available. | Whether sold-device installations also create or link an Installation Note is decided in ARCHITECTURE §7. |
| Workflow | Native Frappe `Workflow` available. | Option for job transitions in #19. |
| PDF generation | `Print Format` has a `pdf_generator` field (wkhtmltopdf or Chrome). | One generator must be installed locally before #27. |

**Conclusion:** the local Frappe v16 / ERPNext v16 bench supports everything the architecture needs, using only standard DocTypes and app-level customisation. No ERPNext core changes are required.

### 4.1 How this was verified
1. `git -C apps/{frappe,erpnext} describe --tags` returned `v16.52.0` and `v16.51.1`.
2. A read-only Python inspection of `deployops.local` (`frappe.connect()`; only `get_meta`, `count`, `get_all`; no writes) confirmed the versions, system settings, companies, DocType availability, record counts and the field lists above.
3. `apps/frappe/pyproject.toml` / `package.json` give Python `>=3.14,<3.15` and Node `>=24`. `apps/erpnext/pyproject.toml` gives `frappe >=16.50.0,<17.0.0`.
4. The GitHub API showed a private repo, `main` unprotected, and 0 workflows.

## 5. Install / deployment approach

### 5.1 Installing the app locally
```
bench get-app <path or repo> deployops      # app lives in apps/deployops
bench --site deployops.local install-app deployops
bench --site deployops.local migrate
```

### 5.2 Development flow
```
deployops.local (develop)
   → task branch (task/<issue>-<slug>)
   → tests on deployops.local (bench run-tests --app deployops)
   → owner review and approval of the changes and test output
   → commit and push (only after approval)
   → owner acceptance
```
A GitHub Actions workflow is written in #34 so CI is ready once code is pushed. It runs a fresh `version-16` bench with ERPNext, installs DeployOps on a throwaway site and runs the tests.

### 5.3 Schema and data change rules
- All DocTypes are defined as JSON in the app module, so they are version controlled. No Customize Form changes or DocTypes created through the UI.
- Fields added to ERPNext DocTypes are created by code (`create_custom_fields` in `after_install` plus a patch) and tagged with the DeployOps module. ERPNext core is never edited.
- Data changes go through idempotent patches in `patches.txt`. Each patch is tested on a fresh site and as an upgrade on a site with existing data.
- No fixture contains customer data, credentials or employee personal data.

### 5.4 Backup and rollback (local)
1. Before any `bench migrate` that runs a new patch, run `bench --site <site> backup --with-files`. Backups stay under `sites/<site>/private/backups/` and are never committed.
2. Code rollback: check out the previous commit and run `bench migrate`.
3. Data rollback: restore the site from the pre-migrate backup with `bench --site <site> restore ...`.
4. Do not use `bench remove-app` as a rollback. It drops the DeployOps DocTypes and their data.

## 6. Risks

| # | Risk | Likelihood / impact | Mitigation |
|---|---|---|---|
| R1 | All test data is synthetic, so real serial, Delivery Note and Subscription patterns may differ from what we assume | Confirmed / Medium | Build fixtures from the FUNCTIONAL_SPEC §8 scenarios |
| R2 | `main` is unprotected and there is no CI | Confirmed / Medium | Add CI in #34; enable branch protection (PR required, 1 approving review, CI must pass) before the first push |
| R3 | wkhtmltopdf is not installed, so PDF reports (#27) cannot be rendered yet | Confirmed / Medium | Install wkhtmltopdf 0.12.6 (patched Qt) or use the v16 Chrome generator; decide in #27 |
| R4 | The sample checklist PDF contains credentials and personal data, and `docs/CHECKLIST_SPECS.md` line 3 names the sample customer/site | Confirmed / Medium | Never use the sample in fixtures; anonymise that line before the first push |
| R5 | Local site has a single company | Confirmed / Medium | Permission tests (#12, #35) create a second company |
| R6 | Single local machine: disk failure or WSL reset could lose uncommitted work and local sites | Low / Medium | Regular off-machine copy of the repo (`git bundle create` to another disk); sites can be rebuilt from the repo and fixtures |

## 7. Open questions
None at this time.
