# DeployOps — Jobs (#18 / #39)

**Status:** Approved design, implemented on 2026-10-18. Workflow transitions and approvals are #19. Job-level visibility (#12) is in §4.
**Code:** [`deployops/deployops/doctype/deployops_job/`](../deployops/deployops/doctype/deployops_job/), [`deployops/api/jobs.py`](../deployops/api/jobs.py), [`deployops/security/job_permissions.py`](../deployops/security/job_permissions.py).

A **DeployOps Job** is one intervention (preparation, installation or maintenance) on one or more machines, started from an ERPNext source document.

---

## 1. Data model

**DeployOps Job** — naming `DO-JOB-.YYYY.-.#####`, change history on.

| Field | Notes |
|---|---|
| Job Type | Pre-installation, Installation, Maintenance |
| Status | Starts at **Draft**. Lifecycle values exist, but status can only change through the workflow (#19) |
| Company | Defaults to the source's company; the source must belong to it |
| Planned Date, Assigned Technician, Equipment Category | Planning and assignment |
| Source Type + Source Document | Sales Order, Delivery Note, Subscription, Maintenance Visit or Maintenance Schedule. Checked with the #37 rules. **Cannot be changed after the first save** |
| Customer, Customer Name | Taken from the source |
| Contact + Contact Details, Site Address + Address Details | Read-only snapshot of the source's contact and site at creation |
| Devices | One row per machine |

**DeployOps Job Device** (child table): Item (model), Serial No, Device Status (Pending, In Progress, Completed, Blocked, Cancelled; starts at Pending; changed by the workflow, #19).

## 2. Creating a job

- **Desk:** DeployOps workspace → **Jobs → New**. Choose Job Type, Source Type and Source Document. **As soon as the source is picked**, the form fills in the company (if empty), customer, contact, site and the machines, using `deployops.api.jobs.get_source_details`. Review the rows, then save. The source picker only offers usable sources that hold your equipment.
- **API:** `deployops.api.jobs.make_job(source_doctype, source_name, job_type, company=None, planned_date=None, assigned_technician=None, equipment_category=None)` (POST).

**Devices come from the source** (in the form when the source is picked, and again on the first save if the table is still empty). Both use the same server function, `devices_from_source`:
- one row per serial when the source lists serials (Delivery Note, Maintenance Visit/Schedule);
- for a Sales Order, one row per unit ordered. Units **already delivered** get their serial from the order's submitted Delivery Notes, minus any returned since; the rest stay empty to be picked during preparation (no stock unit is chosen automatically);
- only serial-numbered Items, and only those within the creator's equipment profile;
- a **Subscription** gives no devices: the rented machine is added explicitly.

## 3. Rules (enforced on the server)

| Rule | Detail |
|---|---|
| Usable source | #37 rules: e.g. no draft, closed or on-hold orders, no returns |
| Equipment | Every device is a serial-numbered Item on the source (any serial-numbered Item for a Subscription) |
| Serial No | Exists, belongs to the Item and company; if the source lists serials for that Item (e.g. a Delivery Note), it must be one of them; no duplicates within a job |
| Serial required | **Installation** and **Maintenance**: yes. **Pre-installation**: optional (assigned during preparation; required before readiness sign-off in #19) |
| No double booking | A serial can be on only **one open job of the same type** (open = not Completed or Cancelled) |
| Creator's equipment | A source with none of the creator's equipment is refused; devices outside the creator's profile are refused. Admin is unrestricted |
| Equipment Category | If set, every device must belong to it |
| Assigned Technician | Active user with the DeployOps Technician role and access to every device's equipment |

## 4. Permissions

From the approved matrix ([PERMISSION_MATRIX.md](PERMISSION_MATRIX.md)): Technician read/write; Supervisor create/write/print; Manager create/write/cancel/print/export; Admin create/write/cancel/print/export; **nobody deletes**.

- **Who sees which job (#12):**

| Role | Sees |
|---|---|
| Technician | Only jobs **assigned to them** |
| Supervisor, Manager | Jobs whose machines are **all** within their equipment profile. A job without machines: when its equipment category is theirs, or when it has no category |
| DeployOps Administrator (and System Manager) | Every job |
| Anyone else | No job |

  Judged from the **saved** job (assignee and machines), so editing a job in memory cannot grant or lose access. Revoking a category hides its jobs immediately. Teams or regions ("management scope") are not defined yet; scoping is by equipment only.
- **No way around it:** the same rule applies to the list, report view, `frappe.client.get_list` / `get` / `get_value`, `/api/resource`, form load, link search, `/printview` and **private attachments** on a job (a file attached to a job is downloadable only by users who may read that job). All are tested over real HTTP in `deployops/tests/test_job_visibility.py`.
- **Level-1 fields** (job type, company, source, planned date, assigned technician, equipment category) are visible to all job roles but **only Supervisor, Manager and Admin can change them**. A Technician can fill in device serials but cannot reassign or replan a job.
- The **source and serial pickers** use DeployOps' own queries (`source_link_query`, `serial_link_query`), because DeployOps roles have no direct ERPNext permissions. The serial picker offers the source's serials, or in-stock serials of that Item (any status for Maintenance).

## 5. Tests

| Test file | What it proves |
|---|---|
| `deployops/tests/test_job.py` | Snapshot and devices from a Sales Order (units, no spares), Delivery Note (one row per serial), Subscription (none); unusable source and wrong company refused; `make_job` API; device rules (item not on source, non-serial item, serial not on the delivery, serial of another item, duplicate serial); serial required by job type; no double booking (other job type allowed, allowed again once completed); status locked; equipment category; assignee rules; Supervisor limited to own equipment and refused on a source with none of it; Technician cannot create, sees only assigned jobs, cannot reassign or replan but can fill serials; both pickers |
| `deployops/tests/test_permission_matrix.py`, `test_security_negative.py` | Job DocPerms match the matrix; Job API allowed and refused per the matrix |
| `deployops/tests/test_job_visibility.py` | Supervisor and Manager scoped by equipment (all machines; no-machine jobs by category); Admin sees all; Technician only assigned; document access matches the list; revocation is immediate; users without a DeployOps role see nothing; over HTTP: list, report view, get_list, link search, direct URL, `frappe.client.get`, form load, `get_value`, print and private attachments |

## 6. UAT steps (manual, on the DeployOps Demo data)

1. As a Supervisor with the Cash Recyclers profile: Jobs → New → Pre-installation, Source Sales Order SAL-ORD-2026-00002. Before saving, two CR-460 rows appear: CM460-0002 (delivered) and one empty (its CM460-0003 was returned); customer, contact and site are filled in. Save.
2. Assign Technician tech@test.local and a planned date. Save.
3. Log in as tech@test.local: only this job is listed. Pick serial CM460-0004 on the first row (only in-stock recyclers are offered) and save. Try to change the assigned technician: it does not stick.
4. As Admin: create an Installation job from MAT-DN-2026-00001 — rows CM460-0001 and BBP-0001. Create a second one from the same delivery: refused (double booking).
5. Try a job from SAL-ORD-2026-00004 (On Hold) or MAT-DN-2026-00003 (return): refused.
