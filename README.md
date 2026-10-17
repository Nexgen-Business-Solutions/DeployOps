# DeployOps

[![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Frappe](https://img.shields.io/badge/Frappe-Framework_16-0089FF)](https://frappeframework.com/)
[![ERPNext](https://img.shields.io/badge/ERPNext-16-0089FF)](https://erpnext.com/)
[![MariaDB](https://img.shields.io/badge/MariaDB-10.11-003545?logo=mariadb&logoColor=white)](https://mariadb.org/)
[![Node.js](https://img.shields.io/badge/Node.js-24-339933?logo=nodedotjs&logoColor=white)](https://nodejs.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](#license)

**DeployOps** is a native Frappe application for **equipment preparation, installation, commissioning and maintenance** on top of ERPNext.

It replaces external Jotform checklists with **native Frappe forms** linked directly to existing ERPNext records: Customer, Item, Serial No, Sales Order, Delivery Note, Subscription, Maintenance Schedule and Maintenance Visit. Technicians work from verified customer, product and serial data instead of retyping it. Every checklist, photo, signature and decision is traceable to the physical device and the business document it came from.

> **Status:** early development. The installable app skeleton exists. Business features are built one at a time, following the [roadmap](#roadmap).

---

## Contents

- [Overview](#overview)
- [Core principles](#core-principles)
- [Business journeys](#business-journeys)
- [Architecture](#architecture)
- [Security model](#security-model)
- [Workflow](#workflow)
- [Checklists in scope](#checklists-in-scope)
- [Roadmap](#roadmap)
- [Development procedure](#development-procedure)
- [Requirements](#requirements)
- [Installation](#installation)
- [Local development](#local-development)
- [Testing](#testing)
- [Code quality](#code-quality)
- [Project structure](#project-structure)
- [Documentation](#documentation)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

DeployOps centralises the technical lifecycle of equipment such as **Cashmatic** cash-management machines and **PUDU BellaBot Pro** robots inside ERPNext:

| Stage | What happens |
|---|---|
| **Pre-installation** | Customer readiness, device preparation and configuration, assignment of a serial number |
| **On-site installation** | Positioning, power and network, tests, training, customer acceptance and signature |
| **Maintenance** | Component-level cleaning and inspection, results and sign-off |

### Where DeployOps fits

```text
┌───────────────────────────────────────────────────────────────┐
│                        ERPNext 16                             │
│                                                               │
│  Customer · Contact · Address · Item · Serial No              │
│  Sales Order · Delivery Note · Subscription                   │
│  Maintenance Schedule · Maintenance Visit                     │
└───────────────────────────────┬───────────────────────────────┘
                                │  links, reads, never duplicates
                                ▼
┌───────────────────────────────────────────────────────────────┐
│                        DeployOps                              │
│                                                               │
│  Jobs & per-device lines      Equipment access profiles       │
│  Serial allocation history    Versioned native checklists     │
│  Workflow & approvals         Evidence, signatures, reports   │
└───────────────────────────────────────────────────────────────┘
```

ERPNext stays the **system of record** for commercial, stock and maintenance data. DeployOps adds the operational layer.

---

## Core principles

These come from the approved product rules in [`AGENTS.md`](AGENTS.md) and [`ROADMAP.md`](ROADMAP.md). They are not optional.

- **Native Frappe forms**, never embedded Jotform.
- **No second master data.** ERPNext Customer, Contact, Address, Item, Serial No and the sales, delivery, subscription and maintenance documents remain the primary records.
- **Serial No is the identity of each physical device.**
- **Subscription is for billing only.** Rental billing uses ERPNext Subscription. DeployOps separately tracks which serial is allocated, returned or swapped.
- **Reuse ERPNext maintenance.** Build on Maintenance Visit and Maintenance Schedule, not a parallel system.
- **Generic roles only:** Technician, Supervisor, Manager, Administrator. There are no supplier-named roles.
- **Server-side, deny-by-default security**, covering DocTypes, queries, APIs, prints, downloads and evidence files.
- **Devices are independent.** Several machines on one Delivery Note can have different installation outcomes.
- **No secrets in records.** Passwords, OTPs, pairing codes and other secrets are never stored in remarks, PDFs, logs or attachments.
- **ERPNext core is never modified.** All changes live in this app.

---

## Business journeys

### Sold equipment
```text
Submitted Sales Order
   → pre-installation job (customer readiness, device preparation)
   → eligible Serial No assigned before machine preparation sign-off
   → submitted Delivery Note (actual dispatched serials)
   → on-site installation, tracked per device
   → evidence, signatures, review → completed
```

### Rented equipment
```text
Subscription (recurring billing only)
   → explicit allocation of a physical Item / Serial No
   → pre-installation → on-site installation
   → return or swap → allocation closed
```
DeployOps never infers a device from a rental service item. It never moves stock or edits submitted Delivery Notes to represent a rental.

### Maintenance
```text
Maintenance Visit (and Maintenance Schedule where present)
   → component-level checklist per serial
   → results, exceptions, signatures
   → linked back to the same visit (no duplicate visits)
```

---

## Architecture

```text
┌───────────────────────────────────────────────┐
│           Frappe Desk (native forms)          │
│   DocType forms · list views · print formats  │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│            DeployOps (Python app)             │
│  Controllers & validation · permission hooks  │
│  Workflow rules · patches · whitelisted APIs  │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│          ERPNext 16 / Frappe 16 (v16)         │
│  Serial and Batch Bundle · Subscription       │
│  Maintenance Visit · Stock ledger (read only) │
└───────────────────────────────────────────────┘
```

### Planned objects
These are **candidates**. Final schemas are decided in #18 and #20 before they are created.

| Object | Responsibility | Issues |
|---|---|---|
| DeployOps Job | Central record: source document, customer and site, intervention type, technician, planned date, state | #18 |
| DeployOps Job Device | One Item / Serial No per line, with its own installation status | #16, #18 |
| Equipment Category & Access Profile | Categories and models a user is authorised for | #10–#12 |
| Equipment Allocation / Event | Reserved, deployed, returned and swapped history, and conflict prevention | #14, #15 |
| Checklist Template / Item | Versioned checklist definition with typed fields and rules | #20 |
| Checklist Response / Result | Answers, evidence, signatures, actor and timestamp, linked to template version, job and device | #21 |

### ERPNext v16 facts the design relies on
Verified in [`docs/COMPATIBILITY_REPORT.md`](docs/COMPATIBILITY_REPORT.md).
- Delivery Note serials are read from **Serial and Batch Bundle** entries.
- **Subscription has no item or serial field**, so rental devices need an explicit allocation record.
- **Maintenance Visit Purpose** carries `item_code` and `serial_no`, so maintenance checklists link per serial.
- DeployOps **reads** Serial No. It never writes `status`, `warehouse` or `customer`.

---

## Security model

Effective access is the **intersection** of three dimensions:

```text
 Operational role         ∩   Equipment access profile   ∩   Job assignment / scope
 (what actions)               (which categories/models)      (which exact jobs)
 Technician, Supervisor,      configured per user            assigned or managed
 Manager, Administrator
```

All three are enforced **on the server** and apply to:
- list views and direct document URLs;
- reports and custom APIs;
- print formats, exports and attachment downloads;
- user revocation and company boundaries.

Hiding a menu item is not security.

---

## Workflow

Proposed lifecycle, subject to owner sign-off in #19:

```text
Draft → In Preparation → Ready for Deployment → On Site / In Progress → Pending Review → Completed
                │                                      │
                └──────────── Blocked ◄────────────────┘      Returned for Correction · Cancelled
```

- Every transition records the actor, the timestamp and the validation result.
- Critical findings or a **NO GO** decision block progression unless an authorised override is approved.
- Devices on the same job can complete independently.

---

## Checklists in scope

| Feature | Checklist | Source |
|---|---|---|
| #22 | Cashmatic pre-installation | [Jotform 253063954693264](https://form.jotform.com/253063954693264) |
| #23 | Cashmatic on-site installation | [Jotform 253064644317254](https://form.jotform.com/253064644317254) |
| #24 | BellaBot Pro pre-installation (GO / GO WITH CONDITIONS / NO GO) | [Jotform 262743846222055](https://form.jotform.com/262743846222055) |
| #25 | BellaBot Pro on-site installation | [Jotform 262743396548066](https://form.jotform.com/262743396548066) |
| #26 | Cashmatic maintenance | [Jotform 253383306590256](https://form.jotform.com/253383306590256) |

Each checklist is implemented only after its field and condition mapping (#40) is approved. Field details are in [`docs/CHECKLIST_SPECS.md`](docs/CHECKLIST_SPECS.md).

---

## Roadmap

Work is tracked on [GitHub Project #39](https://github.com/orgs/Nexgen-Business-Solutions/projects/39) as **Epic → Feature → Task**. Each milestone has an exit gate that must be met before the next starts.

| Milestone | Scope | Issues | Exit gate | Status |
|---|---|---|---|---|
| **M0** Compatibility & plan | Versions, environment, approach | #8, #33 | Compatibility report approved | ✅ Done |
| **M1** Installable app | App skeleton, workspace, tests, CI | #9, #34 | App installs on a local test site; tests and CI baseline in place | 🔄 In progress |
| **M2** Security + ERPNext links | Roles, equipment profiles, job permissions; source lookups; serial allocation; Delivery Note and Maintenance links | #10–#17, #35–#38 | Permission matrix and source lookups tested; allocation design approved | ⏳ Planned |
| **M3** Jobs + checklist framework | Job model, transitions, typed versioned checklists, evidence and signatures | #18–#21, #39–#41 | Jobs, transitions, typed answers and evidence work end to end in test | ⏳ Planned |
| **M4** Cashmatic end-to-end | Pre-installation and on-site checklists | #22, #23, #42, #43 | Sale → preparation → Delivery Note → signed installation | ⏳ Planned |
| **M5** BellaBot + maintenance | Robot checklists, rental device mapping, maintenance checklist | #24–#26 | GO decision, rental mapping and maintenance checklist pass UAT | ⏳ Planned |
| **M6** Reporting & release | Printable reports, audit trail, security and UAT suite, release docs | #27, #30, #32, #44 | Reports, permission test suite and UAT signed off | ⏳ Planned |

### Dependency order
```text
#8 → #9 → #10–#12 (security) ─┐
          #13–#17 (ERPNext) ──┼→ #18–#19 (jobs, workflow) → #20 → #21 (checklists, evidence)
                              │                                      │
                              └──────────────────────────────────────┴→ #22–#26 → #27, #30, #32
```
Blocked issues are never skipped.

---

## Development procedure

Every feature follows the same steps (from [`AGENTS.md`](AGENTS.md)):

1. **Read** the epic, feature, tasks, acceptance criteria and blockers.
2. **Inspect** the current app code and the real ERPNext v16 schema. Never assume fields.
3. **Propose a plan:** data model, flows, affected files, security boundary, tests, migrations, risks and decisions needed.
4. **Resolve** unclear business rules with the product owner **before** coding.
5. **Implement** on a local feature branch: `feature/<issue>-<short-name>`, for example `feature/22-cashmatic-preinstallation`.
6. **Test** success, failure, validation, permissions, multiple devices and migrations on `deployops-test.local`.
7. **Review:** the owner reviews the diff and the test output. **Nothing is committed or pushed before approval.**
8. **Accept:** fresh install or migrate on `deployops-uat.local`, run the UAT scenarios, owner sign-off.
9. Issue status is updated only after acceptance.

### Definition of Done
- Requirements resolved and linked to the parent issue.
- DocTypes and migrations implemented with safe defaults.
- Server-side authorization, state transitions and validation covered by tests.
- Normal, invalid, blocked and multiple-device scenarios tested locally.
- Review notes, affected files and test evidence recorded.
- Owner approval.

---

## Requirements

| Component | Version |
|---|---|
| Frappe Framework | **v16** (`>=16.50.0,<17.0.0`) |
| ERPNext | **v16** |
| Python | 3.14 |
| Node.js | 24+ |
| Yarn | 1.22+ |
| MariaDB | 10.11+ |
| Redis | 7+ |
| PDF generator | wkhtmltopdf 0.12.6 (patched Qt) or the Frappe v16 Chrome generator, needed for printable reports (#27) |

ERPNext must be installed on the site before DeployOps.

---

## Installation

From the bench directory:

```bash
bench get-app git@github.com:Nexgen-Business-Solutions/DeployOps.git --branch main
bench --site <your-site> install-app deployops
bench --site <your-site> migrate
```

- The repository is called `DeployOps`, but the app is called `deployops`. `bench get-app` renames the folder to `apps/deployops` automatically.
- The repository is private. Use an SSH key or a personal access token for a GitHub account with access.

Check the result:

```bash
bench --site <your-site> list-apps
```

---

## Local development

All development happens on a local bench. There is no hosted environment.

| Site | Purpose |
|---|---|
| `deployops.local` | Day-to-day development and demos |
| `deployops-test.local` | Automated tests (`allow_tests: true`) |
| `deployops-uat.local` | Fresh install and UAT scenarios |

```bash
cd ~/frappe/massarie_project
bench start                                   # run the dev server
bench --site deployops.local migrate          # apply schema and patches
bench --site deployops.local clear-cache
```

### Schema and data rules
- DocTypes are defined as JSON in this app. **Do not** create them with Customize Form or through the UI.
- Fields on ERPNext DocTypes are added by code (`create_custom_fields` plus a patch). ERPNext core is never edited.
- Data changes go through idempotent patches listed in `deployops/patches.txt`.
- Fixtures must never contain customer data, credentials or employee personal data.

### Backup and rollback (local)
```bash
bench --site <site> backup --with-files       # before any migrate that runs a new patch
git checkout <previous-commit> && bench --site <site> migrate      # code rollback
bench --site <site> restore <path-to-sql.gz>  # data rollback
```
Do **not** use `bench remove-app` as a rollback. It deletes the DeployOps DocTypes and their data.

---

## Testing

```bash
bench --site deployops-test.local set-config allow_tests true
bench --site deployops-test.local run-tests --app deployops
```

- Tests create their own anonymised data: company, serialised items, customers, orders, deliveries, subscriptions and maintenance visits.
- Permission tests always include a user **without** the right role, profile or assignment.
- CI is defined in `.github/workflows/` and runs on a fresh v16 bench with ERPNext.

---

## Code quality

This app uses [`pre-commit`](https://pre-commit.com/):

```bash
cd apps/deployops
pre-commit install
pre-commit run --all-files
```

Configured tools:
- **ruff:** lint and format, with tabs, double quotes and line length 110;
- **prettier** and **eslint** for JavaScript;
- **pre-commit-hooks**: trailing whitespace, merge conflicts, AST, JSON, TOML, YAML and debug statements.

---

## Project structure

```text
deployops/                       ← repository root (apps/deployops)
├── .github/workflows/           ← CI and linters
├── docs/
│   ├── ARCHITECTURE.md
│   ├── CHECKLIST_SPECS.md
│   ├── COMPATIBILITY_REPORT.md
│   └── FUNCTIONAL_SPEC.md
├── deployops/                   ← Python package
│   ├── deployops/               ← "DeployOps" module (DocTypes, workspace)
│   ├── config/
│   ├── patches/
│   ├── public/
│   ├── templates/
│   ├── hooks.py
│   ├── modules.txt
│   └── patches.txt
├── AGENTS.md                    ← rules for AI-assisted development
├── ROADMAP.md
├── README.md
├── license.txt
└── pyproject.toml
```

---

## Documentation

| Document | Purpose |
|---|---|
| [`ROADMAP.md`](ROADMAP.md) | Mission, governance, phases and sequencing rules |
| [`docs/FUNCTIONAL_SPEC.md`](docs/FUNCTIONAL_SPEC.md) | Business journeys, actors, workflow, UAT scenarios |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Data ownership, candidate objects, permissions, lifecycle |
| [`docs/CHECKLIST_SPECS.md`](docs/CHECKLIST_SPECS.md) | Source mapping for the five checklists |
| [`docs/COMPATIBILITY_REPORT.md`](docs/COMPATIBILITY_REPORT.md) | Verified versions, environments, ERPNext v16 findings, risks |
| [`AGENTS.md`](AGENTS.md) | Instructions for AI coding assistants |

Where these documents disagree, work stops until the product owner decides.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `install-app` says ERPNext is missing | Install ERPNext v16 on the site first |
| App not listed after install | `bench --site <site> list-apps`; check `sites/apps.txt` contains `deployops` |
| Python import errors | `bench setup requirements` |
| Missing assets or stale UI | `bench build --app deployops` then `bench --site <site> clear-cache` |
| Schema changes not applied | `bench --site <site> migrate` |
| PDF printing fails | Install wkhtmltopdf 0.12.6 (patched Qt) or switch the Print Format to the Chrome generator |

---

## Contributing

1. Pick the next **unblocked** feature from Project #39 and read its issue chain.
2. Propose a plan before coding and resolve open business rules with the owner.
3. Work on a local `feature/<issue>-<name>` branch.
4. Run `pre-commit run --all-files` and the test suite.
5. Get owner review and approval before committing.
6. Never commit credentials, Jotform submission data or real customer data.

---

## License

MIT. See [`license.txt`](license.txt).
