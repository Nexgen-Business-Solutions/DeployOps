# DeployOps — Instructions for AI Coding Agents

This file governs AI-assisted engineering in the **DeployOps** Frappe application repository. Human developer: **@Nexgen-Kimbi**. GitHub project: https://github.com/orgs/Nexgen-Business-Solutions/projects/39.

## Authority and requirements
Read in this order before planning/code:
1. `ROADMAP.md`
2. `docs/FUNCTIONAL_SPEC.md`
3. `docs/ARCHITECTURE.md`
4. `docs/CHECKLIST_SPECS.md`
5. The assigned GitHub **feature** and **task**, linked epic and blocking issues.
GitHub issue acceptance criteria and approved specifications govern implementation. If sources conflict, **stop and request product-owner decision**; do not quietly choose a business rule. Draft/proposed sections are **not approved** requirements.

## First task and sequencing
Start at [#8 Frappe compatibility](https://github.com/Nexgen-Business-Solutions/DeployOps/issues/8), task [#33](https://github.com/Nexgen-Business-Solutions/DeployOps/issues/33). Confirm Frappe and ERPNext versions, Frappe Cloud installation rights, production/staging environments, toolchain, required permissions and backup/rollback method. Submit findings for approval **before** app feature implementation. Then #9 and the dependency graph in ROADMAP.md. Do not skip blocked issues. Follow the organization's existing GitHub Epic/Feature/Task/Bug/Documentation workflow and project columns.

## Non-negotiable product principles
- **Native Frappe forms**, not Jotform embeds.
- Existing ERPNext Customer, Contact, Address, Item, Serial No, Sales Order, Delivery Note, Subscription, Maintenance Schedule and Maintenance Visit stay the primary business records. Never create a second item/serial/customer master.
- ERPNext **Serial No** is canonical physical-device identity. Subscriptions handle rental billing, **not** serial allocation; DeployOps must track allocation, return, swaps and conflicts independently of billing.
- Use **generic roles** (Technician, Supervisor, Manager, Administrator), **equipment access profiles** and **job-level assignments** together. No roles named after Cashmatic, PUDU or other suppliers.
- Access enforced **server side** for DocType access, queries, API, print/downloads and evidence files—not merely menu filtering. Deny by default.
- Reuse ERPNext Maintenance Visit and Maintenance Schedule; do not build a parallel maintenance system.
- Multiple machines/serials on one delivery may have independent installation outcomes.
- Preserve technical steps, conditional decisions and evidence from source checklists once verified.
- Never store passwords, OTPs, activation pairing codes or secrets in free text, PDFs, logs or ordinary attachments. Use an approved secrets workflow if required.
- Existing experimental `Cashmatic Installation` DocType is slated for retirement **only after** dependency audit, backup and explicit owner authorization. Never delete it as an incidental migration.

## Development protocol per feature
1. Check linked epic, feature, tasks, acceptance criteria and blockers.
2. Inspect current app code, target ERPNext schemas and environment—do not assume DocType fields or behavior.
3. Propose a short plan: data model, flows, affected files, security boundary, tests, migrations, risks, decisions needed.
4. Resolve ambiguous/unspecified business behavior with the owner before coding.
5. Implement on a feature branch, using Frappe best practices and upgrade-safe conventions (avoid modifying ERPNext core).
6. Add tests for success, failure, validation, permissions, multiple devices, and relevant migrations; run available checks.
7. Open a PR referencing issue IDs, with changes, test evidence, screenshots when relevant, rollout/rollback impacts and remaining risks.
8. Request review; update issue and task states truthfully. Do **not** mark complete before acceptance.
9. Deploy only to a non-production environment unless production is explicitly approved.

## Quality gates
- Schema migrations reversible/backup-safe and tested on an isolated site.
- User, role, equipment profile, assignment, company and document permission boundaries verified, including report/API/attachment download.
- Completed checklist answer history must be traceable to immutable template version and original business records.
- Protect secrets and PII in logs, attachments and PDFs; ensure customer signatures and photos are only visible to permitted staff.
- Use machine-specific Item/Serial validation and avoid double booking equipment.
- Avoid introducing generic dynamic-form technology if native product-specific DocTypes are more reliable; document architecture choice in #20.
- All five checklists need source-based field mapping and sign-off (#40); do not assume original builder validation can be deduced from completed PDFs.

## AI working style
You are a coding assistant, not a substitute product owner. Distinguish **confirmed fact**, **proposal**, **open question**. Never claim tests ran or changes were deployed unless verified. Never commit credentials, Jotform submission secrets or real customer data to this repository. Keep PRs reviewable and aligned to one feature.
