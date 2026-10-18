# DeployOps

[![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Frappe](https://img.shields.io/badge/Frappe-Framework_16-0089FF)](https://frappeframework.com/)
[![ERPNext](https://img.shields.io/badge/ERPNext-16-0089FF)](https://erpnext.com/)
[![MariaDB](https://img.shields.io/badge/MariaDB-10.11-003545?logo=mariadb&logoColor=white)](https://mariadb.org/)
[![Node.js](https://img.shields.io/badge/Node.js-24-339933?logo=nodedotjs&logoColor=white)](https://nodejs.org/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-6-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-8-646CFF?logo=vite&logoColor=white)](https://vite.dev/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](#license)

**DeployOps** is a native Frappe application for **equipment preparation, installation, commissioning and maintenance** on top of ERPNext.

It replaces external Jotform checklists with **native Frappe DocTypes** linked directly to existing ERPNext records: Customer, Item, Serial No, Sales Order, Delivery Note, Subscription, Maintenance Schedule and Maintenance Visit. Technicians work from verified customer, product and serial data instead of retyping it. Every checklist, photo, signature and decision is traceable to the physical device and the business document it came from.

DeployOps has two user interfaces on the same site:
- a **React frontend** served at `/`, for day-to-day operational work;
- **Frappe Desk** at `/desk`, for administration and configuration.

Both read and write the same DocTypes through Frappe's server-side permissions.

> **Status:** early development. The installable app skeleton exists. Business features are built one at a time, following the [roadmap](#roadmap).

---

## Contents

- [Overview](#overview)
- [Core principles](#core-principles)
- [Business journeys](#business-journeys)
- [Architecture](#architecture)
- [Frontend (React)](#frontend-react)
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

- **Native Frappe data model**, never embedded Jotform. Every form is backed by a DeployOps DocType, whether it is shown in the React frontend or in Desk.
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
┌──────────────────────────────┐   ┌───────────────────────────────┐
│   React frontend  ( / )      │   │   Frappe Desk  ( /desk )      │
│ React 19 · TypeScript · Vite │   │ DocType forms · list views    │
│ frappe-react-sdk             │   │ print formats · admin/config  │
└──────────────┬───────────────┘   └───────────────┬───────────────┘
               │  /api (session + CSRF)            │
┌──────────────▼───────────────────────────────────▼───────────────┐
│                     DeployOps (Python app)                       │
│   Controllers & validation · permission hooks · whitelisted APIs │
│   Workflow rules · patches                                       │
└────────────────────────────────┬─────────────────────────────────┘
                                 │
┌────────────────────────────────▼─────────────────────────────────┐
│                    ERPNext 16 / Frappe 16 (v16)                  │
│   Serial and Batch Bundle · Subscription · Maintenance Visit     │
│   Stock ledger (read only)                                       │
└──────────────────────────────────────────────────────────────────┘
```

All business rules and permission checks live in the Python app. The React frontend is a client only: it never decides who may see or change what.

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

## Frontend (React)

The operational UI is a React single-page app in [`frontend/`](frontend/). It was scaffolded with [Doppio](https://github.com/NagariaHussain/doppio) (`bench add-spa`).

| Item | Value |
|---|---|
| Stack | React 19, TypeScript 6, Vite 8, `frappe-react-sdk`, oxlint |
| Source | `frontend/src/` |
| Served at | `/` on the site, e.g. `http://deployops.local:8004/` |
| Desk | `/desk` (`/app` redirects there) |
| Build output | `deployops/public/frontend/` and `deployops/www/frontend.html` (generated, git-ignored) |
| Page controller | `deployops/www/frontend.py` (login check, CSRF token, boot data) |

### URL routing
Set in `deployops/hooks.py`:

| URL | Served by |
|---|---|
| `/` | React (`home_page = "frontend"`) |
| `/<anything>` | React (catch-all `website_route_rules`) |
| `/login`, `/update-password`, `/printview`, `/message` | Frappe (explicit rules listed before the catch-all) |
| `/desk/...`, `/app/...` | Frappe Desk |
| `/api/...`, `/assets/...`, `/files/...`, `/private/...` | Frappe (never routed to React) |

If another Frappe website page has to stay reachable, add an exact rule for it **above** the catch-all. Otherwise React serves it.

### Authentication
- `frontend.py` redirects guests to `/login?redirect-to=<requested path>`. The React page is never served to a user who isn't logged in.
- Every request to `/api` runs with the user's session and CSRF token, so DocType permissions, permission hooks and equipment/job restrictions apply exactly as in Desk.

### Commands
```bash
# from apps/deployops
yarn install                 # installs root and frontend/ dependencies (postinstall)
yarn dev                     # Vite dev server on :8080 with hot reload
yarn build                   # production build into deployops/public/frontend
```
- **Dev server:** `bench start` must be running. Open `http://deployops.local:8080`. The dev server proxies `/app`, `/api`, `/assets`, `/files` and `/private` to the bench web server, on the port read from `sites/common_site_config.json` (`webserver_port`).
- **Production build:** `bench build` (or `bench build --app deployops`) also runs `yarn build` for this app, because the root `package.json` has a `build` script.

### Frontend rules
- No permission logic in React. Hide buttons for usability if needed, but the server must refuse the action anyway.
- No secrets, passwords, OTPs or pairing codes in frontend state, local storage, logs or bundles.
- Talk to Frappe only through `/api` (resources and whitelisted methods). Never bypass DocType validation.

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
5. **Implement** on a task branch: `task/<issue>-<short-name>`, for example `task/34-bootstrap-tests-install-workspace`. Never push directly to a feature branch.
6. **Test** success, failure, validation, permissions, multiple devices and migrations on `deployops.local`.
7. **Review:** the owner reviews the diff and the test output. **Nothing is committed or pushed before approval.**
8. **Accept:** the owner signs off after checking the change on `deployops.local`.
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
bench build --app deployops        # builds the React frontend too
```

- The repository is called `DeployOps`, but the app is called `deployops`. `bench get-app` renames the folder to `apps/deployops` automatically.
- The repository is private. Use an SSH key or a personal access token for a GitHub account with access.

Check the result:

```bash
bench --site <your-site> list-apps
```

Then open `http://<your-site>:<port>/` for the React frontend, or `/desk` for Frappe Desk.

---

## Local development

All development and testing happens on the local site `deployops.local`. There is no hosted environment.

```bash
cd ~/frappe/massarie_project
bench start                                   # run the dev server
bench --site deployops.local migrate          # apply schema and patches
bench --site deployops.local clear-cache

cd apps/deployops && yarn dev                 # React dev server on :8080 (needs bench start)
```

| URL | What |
|---|---|
| `http://deployops.local:8004/` | Built React frontend, served by Frappe |
| `http://deployops.local:8004/desk` | Frappe Desk |
| `http://deployops.local:8080/` | React dev server with hot reload |

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
bench --site deployops.local set-config allow_tests true
bench --site deployops.local run-tests --app deployops
```

Each test runs inside a transaction that is rolled back afterwards, so test data does not remain on the site.

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

Pre-commit does not check `.ts` / `.tsx` files. For the React frontend, run:

```bash
cd frontend
yarn lint                    # oxlint
npx tsc -b                   # type check (vite build does not type-check)
```

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
├── frontend/                    ← React SPA (source)
│   ├── src/
│   ├── index.html
│   ├── package.json
│   ├── proxyOptions.ts          ← dev-server proxy to the bench
│   └── vite.config.ts
├── deployops/                   ← Python package
│   ├── deployops/               ← "DeployOps" module (DocTypes, workspace)
│   ├── config/
│   ├── patches/
│   ├── public/
│   │   └── frontend/            ← React build output (generated, git-ignored)
│   ├── templates/
│   ├── tests/
│   ├── www/
│   │   ├── frontend.py          ← page controller for the React app
│   │   └── frontend.html        ← React entry page (generated, git-ignored)
│   ├── hooks.py
│   ├── modules.txt
│   └── patches.txt
├── AGENTS.md                    ← rules for AI-assisted development
├── ROADMAP.md
├── README.md
├── license.txt
├── package.json                 ← yarn scripts: dev, build, postinstall
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
| `/` shows a blank page or 404 | The frontend was never built: `bench build --app deployops` (or `yarn build`) |
| A Frappe page (e.g. `/me`) opens the React app | Add an exact rule for it above the catch-all in `website_route_rules`, then `bench --site <site> clear-cache` |
| Route changes in `hooks.py` have no effect | `bench --site <site> clear-cache`. Route rules are cached |
| `yarn dev` API calls fail | `bench start` must be running; the proxy reads `webserver_port` from `sites/common_site_config.json` |

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
