# DeployOps — Jobs (#18 / #39)

**Status:** Approved design, implemented on 2026-10-18. Job-level visibility (#12) is in §4; the workflow (#19) in §5.
**Code:** [`deployops/deployops/doctype/deployops_job/`](../deployops/deployops/doctype/deployops_job/), [`deployops/api/jobs.py`](../deployops/api/jobs.py), [`deployops/security/job_permissions.py`](../deployops/security/job_permissions.py).

A **DeployOps Job** is one intervention (preparation, installation or maintenance) on one or more machines, started from an ERPNext source document.

---

## 1. Data model

**DeployOps Job** — naming `DO-JOB-.YYYY.-.#####`, change history on.

| Field | Notes |
|---|---|
| Job Type | Pre-installation, Installation, Maintenance |
| Status | Starts at **Draft**; changes only through the workflow (§5). Also **Status Before Block** (hidden) and the **Status Log** table |
| Company | Defaults to the source's company; the source must belong to it |
| Planned Date, Assigned Technician, Equipment Category | Planning and assignment |
| Source Type + Source Document | Sales Order, Delivery Note, Subscription, Maintenance Visit or Maintenance Schedule. Checked with the #37 rules. **Cannot be changed after the first save** |
| Customer, Customer Name | Taken from the source |
| Contact + Contact Details, Site Address + Address Details | Read-only snapshot of the source's contact and site at creation |
| Devices | One row per machine |

**DeployOps Job Device** (child table): Item (model), Serial No, Device Status (Pending, In Progress, Completed, Blocked, Cancelled; starts at Pending; changed only by the workflow, §5).

**DeployOps Job Status Log** (child table): when, by whom, action, from, to, machine (if the action was on one machine), reason.

## 2. Creating a job

- **Desk:** DeployOps workspace → **Jobs → New**. Choose Job Type, Source Type and Source Document. **As soon as the source is picked**, the form fills in the company (if empty), customer, contact, site and the machines, using `deployops.api.jobs.get_source_details`. Review the rows, then save. The source picker only offers usable sources that hold your equipment.
- **API:** `deployops.api.jobs.make_job(source_doctype, source_name, job_type, company=None, planned_date=None, assigned_technician=None, equipment_category=None)` (POST).

**Devices come from the source** (in the form when the source is picked, and again on the first save if the table is still empty). Both use the same server function, `devices_from_source`:
- one row per serial when the source lists serials (Delivery Note, Maintenance Visit/Schedule);
- for a Sales Order, one row per unit ordered. Units **already delivered** get their serial from the order's submitted Delivery Notes, minus any returned since; the rest stay empty to be picked during preparation (no stock unit is chosen automatically);
- only serial-numbered Items, and only those within the creator's equipment profile;
- a **Subscription** gives the machines **allocated** to it (see [ALLOCATIONS.md](ALLOCATIONS.md)); a rental job may only use those.

## 3. Rules (enforced on the server)

| Rule | Detail |
|---|---|
| Usable source | #37 rules (e.g. no draft, closed or on-hold orders, no returns), checked **when the job is created**. Closing or completing the source in ERPNext later does not stop the job |
| Equipment | Every device is a serial-numbered Item on the source (any serial-numbered Item for a Subscription) |
| Serial No | Exists, belongs to the Item and company; no duplicates within a job. Which serials fit depends on the source: a **Delivery Note**'s own serials (a machine added from a later delivery uses that delivery's); a **Subscription**'s allocated machines; a **Sales Order**'s delivered serials, then any reserved for it, and machines from stock **only for units not delivered yet**. The serial picker offers exactly these |
| Serial required | **Installation** and **Maintenance**: yes. **Pre-installation**: optional while preparing; a machine cannot be completed, nor the job submitted, without one |
| No double booking | A serial can be on only **one open job of the same type** (open = not Completed or Cancelled). A **cancelled machine** no longer holds its serial |
| Quantities | No more machines of an Item than the source covers (units ordered, or serials listed) |
| Creator's equipment | A source with none of the creator's equipment is refused; devices outside the creator's profile are refused. Admin is unrestricted |
| Equipment Category | If set, every device must belong to it |
| Assigned Technician | Active user with the DeployOps Technician role and access to every device's equipment. Checked when assigned and when machines change, so revoking the technician's access later does not stop a Manager from cancelling or reassigning |
| Clean creation | A new job is always Draft, with an empty status log and every machine **Pending**, whatever the creator sends |
| Fixed after creation | Company, source, customer, contact and site cannot be changed. The **job type** can only change while the job is Draft |
| Audit history | Existing status-log entries never change, and none are removed; only the workflow adds entries |
| Machines with a checklist | A machine's Item or serial cannot change while it has a live checklist; a Manager cancels the checklist first. Its checklist cannot be changed once the job is Completed or Cancelled, or the machine is cancelled |
| Rentals | A rental machine must be allocated when it's **added**; a later return doesn't block saving or cancelling the job |

## 4. Permissions

From the approved matrix ([PERMISSION_MATRIX.md](PERMISSION_MATRIX.md)): Technician read/write; Supervisor create/write/print; Manager create/write/cancel/print/export; Admin create/write/cancel/print/export; **nobody deletes**.

- **Who sees which job (#12):**

| Role | Sees |
|---|---|
| Technician | Jobs **assigned to them** whose machines are also within their **current** equipment profile (revoking a category hides the job, even while it stays assigned) |
| Supervisor, Manager | Jobs whose machines are **all** within their equipment profile. A job without machines: only when its equipment category is theirs. A job with no machines and no category is unclassified and only administrators see it (deny by default) |
| DeployOps Administrator (and the Administrator user) | Every job. The System Manager role grants nothing extra here |
| Anyone else | No job |

  Judged from the **saved** job (assignee and machines), so editing a job in memory cannot grant or lose access. Revoking a category hides its jobs immediately. Teams or regions ("management scope") are not defined yet; scoping is by equipment only.
- **No way around it:** the same rule applies to the list, report view, `frappe.client.get_list` / `get` / `get_value`, `/api/resource`, form load, link search, `/printview` and **private attachments** on a job (a file attached to a job is downloadable only by users who may read that job). All are tested over real HTTP in `deployops/tests/test_job_visibility.py`.
- **Level-1 fields** (job type, company, source, planned date, assigned technician, equipment category) are visible to all job roles but **only Supervisor, Manager and Admin can change them**. A Technician can fill in device serials but cannot reassign or replan a job.
- The **source and serial pickers** use DeployOps' own queries (`source_link_query`, `serial_link_query`), because DeployOps roles have no direct ERPNext permissions. The serial picker offers the source's serials, or in-stock serials of that Item (any status for Maintenance).

## 5. Workflow (#19)

Approved on 2026-10-18. Enforced on the server (`deployops/workflow/job_workflow.py`); Desk shows only the buttons the current user may use (**Actions** menu, and **Update Machine** for machines).

**Paths per job type**

| Job type | Path |
|---|---|
| Pre-installation | Draft → In Preparation → Pending Review → Completed |
| Installation | Draft → Ready for Deployment → On Site → Pending Review → Completed |
| Maintenance | Draft → On Site → Pending Review → Completed |

Side states for every type: **Blocked**, **Returned for Correction**, **Cancelled**.

**Job actions**

| Action | From | To | Who | Check |
|---|---|---|---|---|
| Start | Draft | first step of the path | Supervisor, Manager | a technician is assigned |
| Arrived on Site | Ready for Deployment | On Site | assigned Technician | — |
| Submit for Review | last working step, or Returned for Correction | Pending Review | assigned Technician | at least one machine Completed; every machine Completed or Cancelled; none Blocked; completed machines have a Serial No |
| Approve | Pending Review | Completed | Supervisor, Manager | same checks again |
| Return for Correction | Pending Review | Returned for Correction | Supervisor, Manager | **reason required** |
| Block | any active state | Blocked | assigned Technician, Supervisor, Manager | **reason required** |
| Unblock | Blocked | the state before the block | Supervisor, Manager | — |
| Cancel Job | any state except Completed / Cancelled | Cancelled | Manager, Admin | **reason required** |

Approvers and cancellers come from the permission matrix (letters "a" and "x"). Every job passes through Supervisor approval; approval only for exceptions can follow once checklists exist (#21).

**Machine actions** (only while the job is In Preparation, On Site or Returned for Correction)

| Action | From | To | Who |
|---|---|---|---|
| Start Machine | Pending | In Progress | assigned Technician |
| Complete Machine | In Progress | Completed (needs a Serial No) | assigned Technician |
| Block Machine | Pending, In Progress | Blocked (**reason**) | assigned Technician, Supervisor, Manager |
| Unblock Machine | Blocked | In Progress | Supervisor, Manager |
| Cancel Machine | Pending, In Progress, Blocked | Cancelled (**reason**) | Supervisor, Manager |

**NO GO / critical findings:** a Blocked machine stops the job from being submitted or approved. The checklist GO / NO GO decision (BellaBot, #24) will plug into the same rule.

**Audit and integrity**
- Every move is written to the job's **Status Log**: when, who, action, from, to, machine, reason.
- Status, machine status, status-before-block and the log **cannot be edited directly** (form, API or import); only the workflow writes them.
- A **Completed or Cancelled job is locked**, and cannot be cancelled.
- **Machines are protected too:** rows can only be removed while the job is Draft (afterwards use Cancel Machine, which is logged with a reason); a Completed or Cancelled machine's Item and Serial No cannot change; while the job is Pending Review the machine list is frozen, so the reviewer approves exactly what was done.
- The user must be able to see the job (§4) to act on it; a Technician acts only on jobs assigned to them.

**API:** `deployops.api.jobs.get_actions(job)`, `job_action(job, action, reason)`, `device_action(job, device, action, reason)` (POST).

## 6. Tests

| Test file | What it proves |
|---|---|
| `deployops/tests/test_job.py` | Snapshot and devices from a Sales Order (units, no spares), Delivery Note (one row per serial), Subscription (none); unusable source and wrong company refused; `make_job` API; device rules (item not on source, non-serial item, serial not on the delivery, serial of another item, duplicate serial); serial required by job type; no double booking (other job type allowed, allowed again once completed); status locked; equipment category; assignee rules; Supervisor limited to own equipment and refused on a source with none of it; Technician cannot create, sees only assigned jobs, cannot reassign or replan but can fill serials; both pickers |
| `deployops/tests/test_permission_matrix.py`, `test_security_negative.py` | Job DocPerms match the matrix; Job API allowed and refused per the matrix |
| `deployops/tests/test_job_integrity.py` | Status-log entries cannot be rewritten or removed (Technician, Supervisor); a new job ignores supplied statuses and history; source snapshot, company and source fixed; job type fixed once started; no more machines than ordered; a cancelled machine frees its serial; a Manager can cancel after the technician's access is revoked. In `test_checklists.py` / `test_allocations.py`: a machine with a checklist cannot change serial; a cancelled job stops checklist edits; a returned rental machine does not block cancelling its job |
| `deployops/tests/test_order_serials.py` | A delivered order offers and accepts only its delivered serials; undelivered units may use stock; an undelivered order still picks from stock; a machine from a later delivery offers that delivery's serials; a subscription offers its allocated machines, not stock |
| `deployops/tests/test_job_workflow.py` | Installation, Pre-installation and Maintenance paths with the status log; closing the source later does not stop the job; start needs a technician; who may do what (Admin does not approve, Supervisor does not cancel, only the assigned Technician arrives and submits); actions must fit the state; reasons required; submit needs every machine done, none blocked, at least one completed; block and unblock back to the previous state; return for correction and resubmit; cancel and the lock on closed jobs; machines only updated while work is under way; status, machine status and log cannot be edited directly; an unassigned technician cannot act; available actions per user; a completed job cannot be cancelled; completed machines frozen; machines only removed in Draft; machine list frozen during review; over real HTTP: GET refused on state-changing methods, guest and other technician refused, 417 for a wrong state or missing reason, 403 for the wrong person, full path to Completed |
| `deployops/tests/test_job_visibility.py` | Supervisor and Manager scoped by equipment (all machines; no-machine jobs by category); Admin sees all; Technician only assigned; document access matches the list; revocation is immediate; users without a DeployOps role see nothing; over HTTP: list, report view, get_list, link search, direct URL, `frappe.client.get`, form load, `get_value`, print and private attachments |

## 7. UAT steps (manual, on the DeployOps Demo data)

1. As a Supervisor with the Cash Recyclers profile: Jobs → New → Pre-installation, Source Sales Order SAL-ORD-2026-00002. Before saving, two CR-460 rows appear: CM460-0002 (delivered) and one empty (its CM460-0003 was returned); customer, contact and site are filled in. Save.
2. Assign Technician tech@test.local and a planned date. Save.
3. Log in as tech@test.local: only this job is listed. Pick serial CM460-0004 on the first row (only in-stock recyclers are offered) and save. Try to change the assigned technician: it does not stick.
4. As Admin: create an Installation job from MAT-DN-2026-00001 — rows CM460-0001 and BBP-0001. Create a second one from the same delivery: refused (double booking).
5. Try a job from SAL-ORD-2026-00004 (On Hold) or MAT-DN-2026-00003 (return): refused.
6. Workflow, on DO-JOB-2026-00003 (Installation, CM460-0004). Supervisor steps in Desk; Technician steps through the API (Technicians have no Desk, and the React job screens are not built yet):
   - sup@test.local: **Actions → Start** → Ready for Deployment.
   - tech@test.local: `POST /api/method/deployops.api.jobs.job_action` with `job=DO-JOB-2026-00003&action=arrive` → On Site.
   - tech@test.local: `GET /api/method/deployops.api.jobs.get_actions?job=DO-JOB-2026-00003` to read the machine row name, then `POST …device_action` with `action=start`, then `action=complete`.
   - tech@test.local: `POST …job_action` with `action=submit` → Pending Review.
   - sup@test.local: **Actions → Return for Correction** (reason); tech submits again; sup **Actions → Approve** → Completed.
   - Open **Status History**: every step with who, when and the reason. Try to edit the completed job: refused.
