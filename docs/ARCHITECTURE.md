# DeployOps — Technical Architecture (Design Baseline)

**Status:** Proposed architecture; subject to verification of actual ERPNext/Frappe versions and data configuration in [#8](../issues/8). No implementation is authorized solely by this document.

## 1. Purpose and boundaries
DeployOps is a custom installable Frappe app supporting technical pre-installation, on-site commissioning/installation, and maintenance checklists. It integrates with existing ERPNext business documents rather than cloning sales, inventory, subscription or maintenance modules. Frappe forms must be native.

### Data ownership / source of truth
| Domain | ERPNext source | DeployOps usage |
|---|---|---|
| Customer and contacts | Customer, Contact, Address | read/resolve links and capture point-in-time confirmed service-site snapshot |
| Equipment product | Item | validate model and category |
| Physical equipment | **Serial No** | authoritative device identity and state; store references and deployment event history |
| Sales | Sales Order; Sales Invoice only where required | commercial confirmation and billing context |
| Sold equipment dispatch | **Delivery Note** | actual delivered items and serialized units; installation handoff |
| Rentals | **Subscription** for recurring invoice generation | link rental terms/billing source; separate serial-level reservation/deployment/return/swap lifecycle |
| Customer maintenance | Maintenance Schedule, Maintenance Visit | scheduling and execution context; attach resulting checklist |
| Current custom experimental DocType | Cashmatic Installation | audit and safely retire separately (#31); never duplicate or depend on it long-term |

**Important:** A customer on a Subscription may be billed for a rental *service Item* while a separate serialized physical Item is allocated. Do not infer the physical serial from the billed service line. Track allocation history even if serial record's customer/status changes over time.

## 2. Logical structure (candidate DocTypes; final schema in #18/#20)
- **DeployOps Job**: one operational request/intervention, source DocType/name, customer, location, type, assignment, lifecycle and links to relevant commercial/maintenance documents.
- **DeployOps Job Device** (child or linked DocType based on permissions): a device-specific line mapping an Item, Serial No and independent state to the job. Several devices can belong to one job.
- **DeployOps Equipment Category / Profile / User Authorization**: administration of product/model eligibility and authorized equipment groups, independent of user roles.
- **DeployOps Deployment Event / Equipment Allocation**: history of reservation, assignment, deployment, return, replacement; enforce no overlapping active allocations where applicable.
- **DeployOps Checklist Template / Template Item**: versioned guidance and questions, typed answers, conditional eligibility, evidence requirements.
- **DeployOps Checklist Response / Response Item**: responses linked to job/device/ERPNext source, snapshots of approved checklist version, answer values, attachments, actor timestamps and sign-off.
Names are architectural candidates, not approved field definitions. Do not create them without reviewing Frappe alternatives and source checklist complexity (#20).

## 3. Identity, permission, provenance
Permission = **operational role** (what actions) + **equipment profile** (which items/models/categories) + **job assignment or management scope** (which interventions). Enforce server-side for read, write, create, transitions, attach/download, list views, exports, print, custom APIs. Test revocation, multi-company boundaries and direct URLs. Product-specific access is configuration, not security-role proliferation.

Store original source links and key metadata, immutable event history and snapshots of customer/site/serial context as it was confirmed at intervention time. A single serial can legitimately have many successive jobs. Prevent concurrent rental allocations without disturbing ERPNext's stock ledger semantics.

## 4. Lifecycle and triggers
### Sold equipment
Submitted/confirmed Sales Order (subject to owner-approved payment gates) -> pre-install job -> serial assignment and preparation -> submitted Delivery Note -> on-site installation per machine -> verification -> completion / ERPNext Installation Note integration decision.

### Rented equipment
ERPNext Subscription links recurring billing only. Approved rental context -> DeployOps assigns physical Item/Serial -> pre-install -> field deployment / installation -> return or replacement -> close allocation. If customer uses Delivery Notes for rented equipment, leverage them; otherwise preserve a native deployment/return event with validated serial and stock implications. **Do not automatically mark stock 'Delivered' or change warehouses without approved ERPNext transactions.**

### Maintenance
Existing Maintenance Visit (and underlying Maintenance Schedule, when applicable) -> assigned technical job or checklist -> component-level maintenance response -> completion linked back to original Maintenance Visit. Avoid creating duplicate visits.

## 5. Workflow states (proposal; owner decision pending)
Draft -> In Preparation -> Ready for Deployment -> On Site / In Progress -> Pending Review -> Completed. Additional: Blocked, Returned for Correction, Cancelled. Blocking validation for unresolved critical conditions or BellaBot pre-install NO GO; define supervisor override policy with owner. Consider per-device status when several machines are on one delivery. Exact transitions and automatic trigger points belong to #19.

## 6. Checklist model
Select between metadata-driven, typed versioned templates and native product-specific DocTypes after checking Jotform field/conditional complexity. Either choice must use native Frappe UI, server-side validation, version traceability, multiple photo evidence, signatures, and safe printable output. Template revision must not silently alter existing submitted responses.

## 7. Technical decisions to verify
- Supported Frappe/ERPNext versions and Cloud plan's custom-app install permissions.
- Environment/backup strategy and database schema migration ownership.
- Is ERPNext's Installation Note appropriate for each sold/rented deployment? Do not force it for rentals.
- Submitted document hooks versus manual creation for jobs; idempotency, retries and source cancellation/returns.
- Source field mapping for Delivery Note's serialized bundles/status on installed ERPNext version.
- Form offline/mobile requirements; attachment size, retention, signing behavior and report rendering.
- Multiple machine job modeling and lifecycle, sensitive logs, and subscription rental fulfillment.
- Whether Asset should be used for owned robots later (not required for V1).

## 8. Engineering guardrails
Upgrade-safe custom app; no unapproved core modifications. Idempotent hooks and backfills; protect Submitted ERPNext documents. Transactional server-side serial validations and concurrency guards. Explicit migrations with tests/rollback. Complete permission tests before enabling generated PDFs and media downloads.

## 9. Backlog anchors
Foundation #8-#9; permissions #10-#12; ERPNext integrations #13-#17; jobs #18-#19; checklist framework #20-#21; product checklists #22-#26; reports #27; tests #30; legacy retirement #31; deployment #32.
