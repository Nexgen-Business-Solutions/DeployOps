# DeployOps — Development Roadmap

## Mission
Native Frappe application for commissioning, on-site installation and maintenance, using existing ERPNext commercial/inventory/support source records. Forms are native DocTypes/UI, not Jotform embeds.

## Governance
- Work in GitHub issues: `[EPIC]` → `[FEATURE]` → `[TASK]`.
- Assignee for initial backlog: @Nexgen-Kimbi.
- All changes via reviewed PR, tests and UAT before deployment. Unknown business rules require approval.
- Board: https://github.com/orgs/Nexgen-Business-Solutions/projects/39

## Source-of-truth constraints
- ERPNext Serial No uniquely identifies each physical device; never duplicate an equipment master.
- Sold equipment uses confirmed Sales Order, later Delivery Note and correct serial-numbered item.
- Rental billing uses ERPNext Subscription; DeployOps tracks which serialized device is deployed, returned or swapped.
- Maintenance uses existing Maintenance Schedule / Maintenance Visit.
- Roles are generic; equipment/model access profiles and job assignment further restrict server-side permissions.
- Existing Cashmatic Installation DocType is experimental and must be retired only after dependency audit/backup and authorization.

## Phased delivery and issue dependencies
1. **Discovery and foundation**: #8 (compatibility) → #9 (app bootstrap). Technical tasks #33 and #34 (confirm exact task numbers on GitHub).
2. **Business data and authorization**: #10–#12 (roles/profiles/job permissions), #13–#17 (ERPNext references, allocations, subscriptions, delivery notes and maintenance).
3. **Operational workflow and native forms**: #18 (jobs), #19 (transitions) and #20 (typed checklist architecture) → #21 (responses/evidence/signatures).
4. **First end-to-end use case**: #22 Cashmatic pre-installation and #23 Cashmatic on-site installation, backed by approved field mapping and samples.
5. **Other checklists**: #24 BellaBot pre-installation, #25 BellaBot on-site installation, #26 Cashmatic maintenance.
6. **Reporting, QA, cleanup, release**: Reports, security tests, experimental DocType retirement and release features.

## Work sequencing rules
- Do not code product-specific checklists until their original source and rules are mapped and approved.
- Each on-site installation must be traceable to one physical serialized device; one Delivery Note may include multiple machines and partial outcomes.
- No-go / blocked outcomes must prevent unauthorized progression.
- Never record device passwords, OTPs or pairing secrets in plain-text remarks, reports or attachments.
- UI hiding is not security: verify restrictions for API, files, reports and direct URLs.

## Definition of Done
Accepted design, linked parent issue, tests, reviewer-approved PR, migration safety, documentation, UAT evidence and successful test-site verification.

## Open questions
- Exact ERPNext/Frappe/Frappe Cloud versions and app installation policy.
- Product-owner approval for original Jotform conditional rules and completed PDF samples.
- Business rule for when sales are considered confirmed and whether payment gates installation.
- Supervisor approvals, blocked-state overrides and offline technician usage.
