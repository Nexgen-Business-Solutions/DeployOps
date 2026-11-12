# v2 Plan 3: DeployOps job connection (implementation plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect `forms_core` forms to DeployOps jobs and machines: Form Rules decide each machine's forms, Supervisors and Managers override them, required forms and form outcomes block the machine, and the APIs that Plan 4's screens need exist with fixed shapes.

**Architecture:** DeployOps registers a context provider for `DeployOps Job`, so every Form Submission on a job is visible exactly when its job is. A **Form Rule** (job type + equipment category → form) plans the forms. A **Job Device Form** child table on the job holds each machine's planned forms. Rows follow the rules until the machine's first form is started, then only overrides change them. The job workflow keeps its v1 checks for machines without Job Device Form rows, and judges machines that have rows by their forms.

**Tech Stack:** Frappe v16 (Python 3.14), ERPNext v16, MariaDB; `forms_core` (branch `task/v2-forms-core-reports`) as a required app.

**Spec:** `docs/superpowers/specs/2026-11-05-v2-form-builder-design.md`:
- §7.1 (the job provider side), §7.2, §7.3
- the DeployOps API in §9
- the Jobs tests in §10
- §12 decisions 6 and 7
- §4 "Who can see them": the Supervisor report access deferred from Plan 2

This plan builds on Plan 1 (`docs/superpowers/plans/2026-11-05-v2-plan-1-forms-core-engine.md`) and Plan 2 (`docs/superpowers/plans/2026-11-08-v2-plan-2-report-tables.md`).

**Not in this plan:**
- React screens. Plan 4 builds the machine screen and cards on the APIs in Task 5 and Task 6.
- Child-table rows (repeating tables) in the Supervisor report. §11 lists "supervisor report screen improvements" as v2.x.
- PDFs (Plan 6).
- The five v1 forms rebuilt (Plan 7).

## Global Constraints

- **Location and branch:**
  - Code lives in `deployops` (`/home/kimbi/frappe/massarie_project/apps/deployops`), branch `task/v2-job-connection`, created from `task/v2-form-builder-spec`.
  - `forms_core` is read-only here. Use its public functions only: `forms_core.context.ContextProvider`, `forms_core.submissions.start` / `triggered_outcomes` / `version_definition`, `forms_core.definition.field_index`, `forms_core.versions.publish`, `forms_core.ids.new_id`, `forms_core.reports.schema.report_doctypes` / `sync_schema` / `drop_report`.
  - Python 3.14, ruff `line-length = 110`, tabs. User-facing messages go through `_()`.
- **Commits:**
  - Local only, with short one-line messages.
  - `git add` explicit paths only. Never add the `.claude/worktrees/...` gitlink.
  - No push and no GitHub activity.
- **Roles:** use the constants in `deployops/roles.py`: `TECHNICIAN` = `DeployOps Technician`, `SUPERVISOR` = `DeployOps Supervisor`, `MANAGER` = `DeployOps Manager`, `ADMINISTRATOR` = `DeployOps Administrator`. No supplier names in any role, rule or DocType name.
- **Hooks** (in `deployops/hooks.py`):
  - `required_apps = ["erpnext", "forms_core"]`
  - `forms_core_context_providers = {"DeployOps Job": "deployops.forms.provider.JobFormProvider"}`
  - `forms_core_designer_roles = ["DeployOps Manager", "DeployOps Administrator"]`
  - `doc_events["Form Submission"] = {"after_insert": "deployops.forms.machine_forms.on_submission_insert"}`
- **v1 coexistence (do not break v1):**
  - The five v1 checklist DocTypes, their controllers, `checklists/cards.py` and every existing test stay as they are.
  - **A machine "uses forms"** when it has at least one Job Device Form row with `removed = 0`. Such a machine is judged only by its forms. Any other machine is judged by v1 exactly as today (`card_for` / `form_for_device`).
  - A machine whose v1 checklist exists (draft or submitted, `form_for_device` not None) never gets Job Device Form rows from rules.
  - v1 `start_checklist` is refused on a machine that uses forms, and v1 auto-creation on job start skips it.
- **Form Submission rights** (`FORM_LETTERS` in `security/matrix.py`). This is the v1 checklist row without `a`, because approve is a workflow move:

  | Role | Letters |
  |---|---|
  | Technician | `rcwsp` |
  | Supervisor | `rp` |
  | Manager | `rxpe` |
  | Administrator | `rpe` |

  - `c`, `w` and `s` count only from the Technician role, and only when the user is the job's saved `assigned_technician`.
  - Ptype → letter:
    - `read`, `select`, `report`, `email` → `r`
    - `print` → `p`, `export` → `e`
    - `create` → `c`, `write` → `w` (an amend arrives as `write`)
    - `submit` → `s`, `cancel` → `x`
  - Any other ptype is denied.
  - `FORM_LETTERS` is **not** a `DOCTYPE_MATRIX` row: Form Submission's DocPerm is role `All`, and the matrix test compares DocPerm.
- **Form Rule rights** (`DOCTYPE_MATRIX["DeployOps Form Rule"]`): Technician `""`, Supervisor `r`, Manager `rcwd`, Administrator `rcwd`. It is also added to `PRINT_CHECKED`.
- **Status Log actions** (written with `job_workflow._log`, saved with `job_workflow._save`):

  | Action | When |
  |---|---|
  | `forms: add` | a form is added to a machine |
  | `forms: remove` | a form is removed from a machine |
  | `form: draft discarded` | a draft is discarded |
  | `form: cancelled` | a submitted form is cancelled |
  | `machine: block` | a `block_machine` outcome (same action v1 uses) |
  | `machine: flagged for review` | a `flag_for_review` outcome |
  | `machine: reopened` | a required form is cancelled on a Completed machine |

  `reason` holds `"<form title>"`, or `"<form title>: <text>"` when there is a reason or a field label.
- **Machine form status** (from the row's `submission`):
  - no submission, or a cancelled one → `Not started`
  - docstatus 0 → `Draft`
  - docstatus 1 → `Submitted`
- **Tests:**
  - Run with `bench --site deployops.local run-tests --app deployops --module deployops.tests.<module>`.
  - Publishing in tests builds no report DocTypes, because `forms_core.reports.jobs.enqueue` is inline only when `frappe.flags.forms_core_report_jobs` is set. Only Task 6's report test sets that flag. DocType DDL commits implicitly, so that test builds its report once in `setUpClass` and drops it in `tearDownClass`.
- **Migrations:** after each schema change, run `bench --site deployops.local migrate && bench --site test.site migrate`.

## Review Focus

1. **Two Start presses at once** (two tabs, or a double tap) on the same machine and form must give one draft, not two. → Task 3 `test_can_start_locks_job_row` and `test_second_start_refused`.
2. **Bypassing DeployOps:** a technician who isn't on the job calls `forms_core.api.get_submission`, `start_submission`, `save_answers`, or downloads a file attached to the submission. Each one is refused. → Task 3 `test_outsider_refused_through_forms_core_api` and `test_attached_file_follows_job`.
3. **A machine with both a v1 checklist and a matching Form Rule:** v1 governs and no rows are added. A machine with rows refuses v1 `start_checklist`. → Task 4 `test_v1_checklist_machine_gets_no_rows` and `test_v1_start_refused_when_machine_uses_forms`.
4. **A Manager edits a Form Rule** while their equipment profile doesn't cover every open job of that type. All unfrozen jobs still resync, with no PermissionError. → Task 2 `test_rule_change_resyncs_jobs_outside_editor_scope`.
5. **A Manager cancels a submitted required form on a Completed machine:** the machine goes back to In Progress and the job can't be approved. → Task 4 `test_cancel_required_on_completed_machine_reopens_it`.

---

## File structure (inside `deployops/deployops/`)

```
forms/__init__.py
forms/rules.py           # categories_for_item, planned_forms, plan_rows (pure)
forms/machine_forms.py   # sync_job, resync_job_type, frozen, uses_forms, missing_required,
                         # row_status, on_submission_insert, apply_outcomes, on_form_cancel
forms/provider.py        # JobFormProvider
api/forms.py             # machine_forms, start_machine_form, override_machine_forms,
                         # discard_machine_form, cancel_machine_form, form_cards, form_jobs, report_rows
deployops/doctype/deployops_form_rule/         # new
deployops/doctype/deployops_job_device_form/   # new child of DeployOps Job
modified: hooks.py, security/matrix.py, deployops_job.json + .py, workflow/job_workflow.py,
          api/checklists.py, api/technician.py, docs/JOBS.md, docs/PERMISSION_MATRIX.md
tests/forms_utils.py, test_forms_rules.py, test_forms_machine.py, test_forms_provider.py,
      test_forms_workflow.py, test_forms_api.py, test_forms_cards.py
```

---

### Task 1: Wiring, Form Rule and planning

**Files:**
- Create:
  - `forms/__init__.py`, `forms/rules.py`, and `forms/provider.py` (the data parts only)
  - `deployops/doctype/deployops_form_rule/` (json, py, `__init__.py`)
  - `tests/forms_utils.py`
- Modify: `hooks.py` (all four hook entries in the Global Constraints, plus `"DeployOps Form Rule"` in `PRINT_CHECKED`), `security/matrix.py`.
- Test: `tests/test_forms_rules.py`.

**DocType `DeployOps Form Rule`:**
- Module `DeployOps`, autoname `hash`.
- Fields:
  - `job_type`: Select, the same options as Job.job_type, reqd
  - `equipment_category`: Link DeployOps Equipment Category, reqd
  - `form`: Link Form, reqd
  - `form_title`: Data, `fetch_from: form.title`, read-only
  - `required`: Check, default 1
  - `sort_order`: Int, default 0
  - `active`: Check, default 1
- DocPerms match the matrix row.
- `validate`:
  - The form's `context_doctype` is `"DeployOps Job"`. Otherwise: "Form {0} is not a job form."
  - The form is not Archived.
  - An active rule needs a `current_version`.
  - No other rule has the same (job_type, equipment_category, form): "This rule already exists."
- `on_update` and `on_trash` call `machine_forms.resync_job_type(job_type)` (Task 2). On update it also resyncs the previous job type when that changed. Until Task 2 lands, guard the call with `if hasattr(...)`. Task 2 removes the guard.

**Interfaces:**
- Produces in `forms/rules.py`:
  - `categories_for_item(item_code: str) -> set[str]`: the enabled categories whose `get_category_items([c])` contains the item.
  - `planned_forms(job_type: str, item_code: str) -> list[dict]`: `[{"form": str, "required": bool, "sort_order": int}]`.
    - Comes from active rules for that job type whose category is in `categories_for_item`, skipping Archived or unpublished forms.
    - One entry per form: `required` is true if any rule says so, and `sort_order` is the lowest.
    - Sorted by (sort_order, form title).
  - `plan_rows(existing: list[dict], planned: list[dict], device: str) -> list[dict]` (pure). `existing` holds row dicts with keys `device, form, required, sort_order, origin, removed, submission, flagged`. It returns that device's new rows, sorted by (sort_order, form):
    - `origin == "Override"` rows are returned unchanged.
    - `origin == "Rule"` rows whose form is planned keep `removed`, `submission` and `flagged`, and take the planned `required` and `sort_order`.
    - `origin == "Rule"` rows whose form is no longer planned are dropped.
    - A planned form with no row gets `{"origin": "Rule", "removed": 0, "submission": None, "flagged": 0}`.
- Produces in `forms/provider.py`: `class JobFormProvider(ContextProvider)` with:
  - `values(context_name, context_row) -> dict`. Keys and sources:
    - From the job: `job` (name), `job_type`, `customer`, `customer_name`, `address` (`address_display`), `contact` (`contact_display`), `company`.
    - `planned_date`: ISO `YYYY-MM-DD`, or None.
    - `technician`: the assigned technician's full name. `technician_user`: their user id.
    - From the machine row: `item_code`, `item_name`, `serial_no`. All three are None when the row is missing.
  - `value_catalog() -> list[dict]`: one entry per key above, with `type` = `"long_text"` for address and contact, `"date"` for planned_date, and `"text"` for the rest.
  - `outcomes() -> list[dict]`: `[{"effect": "block_machine", "label": "Block the machine"}, {"effect": "flag_for_review", "label": "Flag for review"}]`.
  - `can_start`, `has_permission` and `query_conditions` arrive in Task 3. Until then they keep the base class behaviour.
- Produces in `security/matrix.py`: the `DOCTYPE_MATRIX` row and `FORM_LETTERS: dict[str, str]` (Global Constraints).
- Produces in `tests/forms_utils.py`:
  - `publish_job_form(key: str | None = None, outcome: str | None = None) -> dict`.
    - Publishes, as Administrator, a Form with `context_doctype = "DeployOps Job"` and one section: `serial` (text, `fill_from {"value": "serial_no", "locked": True}`), `note` (text, required) and `safe` (yes_no, with `outcomes [{"when": {"field": <safe id>, "op": "eq", "value": "No"}, "effect": outcome}]` when `outcome` is given).
    - Returns `{"form": name, "serial": id, "note": id, "safe": id}`.
  - `add_rule(job_type, category, form, required=True, sort_order=0) -> str`.
  - `class FormJobCase(JobTestCase)`: in `setUp` it publishes two forms (`self.form_a` required, `self.form_b` optional) with rules on `"_Test Cash"` for Installation.

- [ ] **Step 1: Write the failing tests:**
  - `test_hooks_registered`: `frappe.get_hooks("forms_core_designer_roles")` equals `[MANAGER, ADMINISTRATOR]`; `forms_core.context.get_provider("DeployOps Job")` is a `JobFormProvider`; `"forms_core" in frappe.get_hooks("required_apps")`.
  - `test_manager_is_designer_technician_not`: `forms_core.permissions.is_designer` is True for the Manager and Administrator role users and False for the Technician and Supervisor.
  - `test_rule_refuses_non_job_form`, `test_rule_refuses_archived_form`, `test_rule_refuses_duplicate`.
  - `test_planned_forms_union_required_wins`: two categories hold the item. Rule A is optional in category 1 and required in category 2; rule B is optional. The result is `[A required, B optional]`, each listed once.
  - `test_planned_forms_ignores_inactive_disabled_and_other_job_type`.
  - `test_plan_rows_keeps_override_drops_unplanned_rule`.
  - `test_plan_rows_keeps_removed_flag_and_submission`.
  - `test_values_and_catalog`: on a saved job, values for a machine row give its serial and item and the technician's full name, and every key in `values` appears in `value_catalog`.
  - `test_publish_refuses_unknown_effect`: a job form with outcome effect `"explode"` raises `FormValidationError`.
  - No new matrix test: the existing `test_every_deployops_doctype_is_in_matrix`, `test_every_deployops_doctype_checks_the_print_right` and `test_doctype_rights_match_matrix` cover Form Rule once its DocType exists. Step 4 runs them.
- [ ] **Step 2:** Run `--module deployops.tests.test_forms_rules`. Expect FAIL.
- [ ] **Step 3:** Implement. Migrate both sites.
- [ ] **Step 4:** Run `test_forms_rules`, `test_permission_matrix` and `test_matrix_unit`. Expect PASS. Then run `bench --site deployops.local run-tests --app forms_core` and record the result in the task report. **Known risk:** forms_core tests that make a `System Manager` user act as designer (`test_submissions.py` around lines 542 and 829, `test_report_schema.py` line 209) fail once this hook is set. Do not edit forms_core; report the failures (see the open question in the hand-off).
- [ ] **Step 5:** Commit `feat(v2): forms_core wiring and form rules`.

---

### Task 2: Job Device Form and rule sync

**Files:**
- Create: `deployops/doctype/deployops_job_device_form/` (istable).
- Create: `forms/machine_forms.py` (the sync part).
- Modify: `deployops_job.json` (add a Table field `device_forms` → DeployOps Job Device Form, label "Machine Forms", read_only, placed after `devices`), `deployops_job.py`, and the Form Rule controller (remove the Task 1 guard).
- Test: `tests/test_forms_machine.py`.

**DocType `DeployOps Job Device Form`** (child). Every field except `device` and `form` is read-only:
- `device`: Data, reqd. The DeployOps Job Device row name.
- `form`: Link Form, reqd.
- `form_title`: Data, `fetch_from form.title`.
- `required`: Check.
- `sort_order`: Int.
- `origin`: Select `Rule\nOverride`.
- `removed`: Check.
- `submission`: Link Form Submission.
- `flagged`: Check.

**Interfaces:**
- Consumes: `planned_forms`, `plan_rows` (Task 1); `form_for_device` (v1 `checklists/cards.py`).
- Produces in `forms/machine_forms.py`:
  - `frozen(job: str, device: str) -> bool`: a Form Submission exists, of any docstatus, with `context_doctype = "DeployOps Job"`, `context_name = job` and `context_row = device`. A discarded (deleted) draft no longer counts.
  - `sync_job(job_doc) -> None`, which works in memory:
    - Drops rows whose `device` is no longer on the job.
    - Leaves a device's rows untouched when the device is Completed or Cancelled, when the job status is in `CLOSED` or is `Pending Review`, when `frozen` is true, or when `form_for_device` finds a v1 checklist. With a v1 checklist and no rows, nothing is added.
    - Otherwise replaces that device's rows with `plan_rows(existing, planned_forms(job.job_type, row.item_code), row.name)`.
    - Gives any device row without a `name` one first, with `frappe.generate_hash(length=10)`, so rows can point at it before the insert.
  - `resync_job_type(job_type: str) -> int`: loads every job of that type whose status is not in `CLOSED` and not `Pending Review`, runs `sync_job`, and saves only the jobs whose rows changed. The save sets `flags.device_forms_sync = True` and uses `ignore_permissions`. Returns how many jobs were saved.
  - `uses_forms(job_doc, device: str) -> bool` and `active_rows(job_doc, device: str) -> list`: the device's rows with `removed = 0`, in order.
- Modify `DeployOpsJob`:
  - **New job:** `self.set("device_forms", [])` first. Anything the caller sent is dropped.
  - **Existing job:** `validate_device_forms_unchanged()` runs before the sync. Unless `flags.allow_status_change` or `flags.device_forms_sync` is set, the rows must match the saved rows on every field in the DocType list. Otherwise: "Machine forms are set by form rules and overrides."
  - **Every save:** call `machine_forms.sync_job(self)` at the end of `validate`.
  - **Equipment check:** `validate_equipment_access` returns early when `flags.device_forms_sync` is set, the same way it does for `delivery_handoff`.

- [ ] **Step 1: Write the failing tests** (`FormJobCase`):
  - `test_new_job_gets_rows_from_rules`: an Installation job with two cash machines gets 4 rows (A required, B optional per machine), all with origin Rule.
  - `test_several_forms_per_machine_ordered`: `sort_order` 2 on A and 1 on B lists B first.
  - `test_caller_rows_ignored_on_new_job`: rows sent in the insert dict are replaced.
  - `test_rows_cannot_be_edited_directly`: changing `required` or adding a row with `job.save()` raises.
  - `test_rows_follow_rules_until_first_form_started`:
    - Making B required updates the rows.
    - Then a submission is inserted for machine 1 (`frappe.get_doc({...}).insert(ignore_permissions=True)` with `flags.forms_core_start = True`, as Administrator).
    - Then deactivating A changes machine 2's rows but not machine 1's.
  - `test_added_machine_gets_rows_removed_machine_loses_them` (in Draft).
  - `test_completed_and_cancelled_machines_not_resynced`.
  - `test_rule_change_resyncs_jobs_outside_editor_scope`: a Manager whose profile has only `"_Test Cash"` saves a rule, and a job holding a robot machine (outside that profile) of the same job type still resyncs. Saved as that Manager with `set_user`.
- [ ] **Step 2:** Run `--module deployops.tests.test_forms_machine`. Expect FAIL.
- [ ] **Step 3:** Implement. Migrate both sites.
- [ ] **Step 4:** Run `test_forms_machine`, `test_job`, `test_job_integrity` and `test_job_workflow`. Expect PASS.
- [ ] **Step 5:** Commit `feat(v2): machine form rows from rules`.

---

### Task 3: Job provider permissions and start checks

**Files:** Modify `forms/provider.py` and `forms/machine_forms.py` (`on_submission_insert`). Test: `tests/test_forms_provider.py`.

**Interfaces:**
- Consumes: `job_in_scope`, `job_query_conditions` (`security/job_permissions.py`); `CHECKLIST_STATES` (`job_workflow`); `FORM_LETTERS` (Task 1); `active_rows` (Task 2).
- Produces on `JobFormProvider`, with the exact signatures of `forms_core/context.py`:
  - `can_start(context_name: str, context_row: str | None, form: str) -> str | None`.
    - First lock the job: `frappe.db.get_value("DeployOps Job", context_name, "status", for_update=True)`.
    - Then return the first reason that applies, in this order:
      - job missing → "This job does not exist."
      - status not in `CHECKLIST_STATES` → "A form can only be started while the job is being worked on."
      - machine row not on the job → "That machine is not on job {0}."
      - machine Cancelled → "This machine was cancelled on the job."
      - no active row for (row, form) → "This form is not planned for this machine."
      - a Form Submission with docstatus 0 or 1 already exists for (job, row, form) → "This machine already has this form on this job."
    - None otherwise.
  - `has_permission(submission, user: str, ptype: str) -> bool`.
    - False when the job doesn't exist or `job_in_scope(job, user)` is False.
    - Otherwise True only when the user's letters (`FORM_LETTERS`, with the Technician and assignee rule) include the ptype's letter.
    - `create`, `write` and `submit` also need the job status in `CHECKLIST_STATES` and the machine row present and not Cancelled.
    - `cancel` also needs the job status not in `CLOSED` and `frappe.flags.deployops_form_cancel` set (by Task 5's `cancel_machine_form`).
  - `query_conditions(user: str) -> str`:
    - `job_query_conditions(user)`, wrapped as ``"`tabForm Submission`.`context_name` in (select `tabDeployOps Job`.`name` from `tabDeployOps Job` where <cond>)"``.
    - When the job condition is `""` (unrestricted users), return `"1=1"`. forms_core treats an empty string as deny.
- Produces in `machine_forms.py`: `on_submission_insert(doc, method=None) -> None`.
  - For a Form Submission with `context_doctype == "DeployOps Job"`, it sets `submission = doc.name` on the active row for (`context_row`, `form`), with `frappe.db.set_value`.
  - This covers starts and amends.

- [ ] **Step 1: Write the failing tests** (`FormJobCase`, job started to Ready for Deployment or On Site):
  - `test_assigned_technician_starts_saves_submits`: through `forms_core.api` as the technician. The serial is filled and locked, and the row's `submission` is set.
  - `test_can_start_refusals`: one assertion per reason, in the order above.
  - `test_second_start_refused`.
  - `test_can_start_locks_job_row`: patch `frappe.db.get_value` with `wraps`, and assert it is called with `for_update=True`.
  - `test_supervisor_reads_cannot_write_or_start`.
  - `test_manager_reads_cannot_cancel_directly`: `forms_core.api.cancel` raises PermissionError without the flag.
  - `test_unassigned_technician_cannot_write`: a second technician with the same profile.
  - `test_outsider_refused_through_forms_core_api`: a technician not on the job gets PermissionError from `get_submission`, `start_submission` and `save_answers`. `frappe.get_list("Form Submission")` excludes the submission.
  - `test_query_conditions_follow_job_visibility`: the Supervisor's `get_list` includes it. A Supervisor whose profile lacks the category doesn't see it. The Administrator role sees it.
  - `test_attached_file_follows_job`: a private File attached to the submission. `frappe.has_permission("File", "read", file_doc, user=...)` is True for the technician and False for the outsider.
  - `test_write_refused_once_job_pending_review`.
- [ ] **Step 2:** Run `--module deployops.tests.test_forms_provider`. Expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run it again. Expect PASS.
- [ ] **Step 5:** Commit `feat(v2): job form provider permissions`.

---

### Task 4: Outcomes, blocking and machine changes

**Files:**
- Modify:
  - `forms/provider.py` (`on_submit`, `on_cancel`)
  - `forms/machine_forms.py`
  - `workflow/job_workflow.py`
  - `deployops_job.py` (the item-change guard)
  - `api/checklists.py` and `api/technician.py` (v1 coexistence)
- Test: `tests/test_forms_workflow.py`.

**Interfaces:**
- Consumes: `forms_core.submissions.triggered_outcomes(doc) -> list[{"field", "effect"}]`, `forms_core.definition.field_index(definition)`, `version_definition`; `job_workflow._log`, `_save`, `_device_label`.
- Produces in `machine_forms.py`:
  - `missing_required(job_doc, device: str) -> list[str]`: titles of active required rows whose `submission` is not docstatus 1.
  - `row_status(row) -> str`: per the Global Constraints.
  - `has_live_submission(job: str, device: str) -> bool`: docstatus 0 or 1.
  - `apply_outcomes(submission) -> None`, called by `JobFormProvider.on_submit`:
    - Sets `flagged` on the row: 1 if a `flag_for_review` outcome fired, else 0.
    - `block_machine`: unless the machine is Cancelled, set `device_status = "Blocked"` and `blocked_by_checklist = 1`, and log `machine: block` with reason `"<form title>: <field label>"`.
    - `flag_for_review`: log `machine: flagged for review`.
    - Saves with `_save` when anything changed.
  - `on_form_cancel(submission) -> None`, called by `on_cancel`:
    - Logs `form: cancelled` with reason `frappe.flags.deployops_form_cancel`, and clears `flagged`.
    - When the row is required and the machine is Completed, it sets `In Progress` and logs `machine: reopened`.
    - A block stays: unblocking it is an approver's action with a reason, as in v1.
- Produces in `job_workflow.py`: `_forms_problem(job, row) -> str | None`.
  - If `uses_forms(job, row.name)`: "the required form {0} of machine {1} is not submitted", using the first title from `missing_required`, or None when nothing is missing.
  - Otherwise the v1 result: "the checklist of machine {0} is not submitted" when `_checklist_not_submitted` is true.
  - `_job_check` uses it in place of its `_checklist_not_submitted` branch.
  - `apply_device_action("complete")` refuses with "Submit the required form {0} of machine {1} before completing it." for v2 machines, and keeps the v1 message for v1 machines.
  - `_create_checklists` skips machines that use forms. `_checklist_not_submitted` itself is unchanged.
- **Machine changes** (`validate_workflow_fields_unchanged`): when `row.item_code` changes and `has_live_submission(job, row)` is true, raise "Row #{0}: this machine has forms; a manager must cancel or discard them before the machine can be changed." A serial-only change is allowed under the existing guards.
- **v1 entry points:**
  - `start_checklist` throws "This machine uses forms from the form builder." when `uses_forms`.
  - `_machine` in `api/technician.py` adds `"uses_forms": bool`, and `can_start_checklist` becomes false when it is true.

- [ ] **Step 1: Write the failing tests:**
  - `test_machine_cannot_complete_until_required_forms_submitted`: optional B is unsubmitted and A is submitted, so complete succeeds.
  - `test_job_cannot_be_submitted_with_missing_required_form`.
  - `test_block_outcome_blocks_machine_and_unblock_needs_reason`: a form with outcome `block_machine`, submitted with `safe = "No"`.
  - `test_flag_outcome_flags_row_without_blocking`.
  - `test_cancel_required_on_completed_machine_reopens_it`: as the Manager through `cancel_machine_form`, or with the flag set directly until Task 5. The machine goes to In Progress, the log has `form: cancelled` and `machine: reopened`, and approve is refused.
  - `test_cancelled_machine_draft_cannot_be_submitted`.
  - `test_serial_swap_draft_follows_submitted_keeps`: on a Pre-installation job, or an Installation job where the serial change is allowed. After the swap, `save_answers(draft, {})` gives the new serial, and the submitted answers keep the old one.
  - `test_item_change_refused_with_live_form`.
  - `test_v1_checklist_machine_gets_no_rows`: create the v1 checklist first, then add a rule for that category, then resync. No rows are added, and the v1 blocking still applies.
  - `test_v1_start_refused_when_machine_uses_forms`.
  - `test_v1_machines_unchanged`: a job with no rules behaves as before. The existing `test_job_workflow` and `test_checklists` stay green.
- [ ] **Step 2:** Run `--module deployops.tests.test_forms_workflow`. Expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `test_forms_workflow`, `test_job_workflow`, `test_checklists`, `test_technician_api`, `test_cashmatic_installation` and `test_bellabot_installation`. Expect PASS.
- [ ] **Step 5:** Commit `feat(v2): form outcomes and machine blocking`.

---

### Task 5: Machine forms API

**Files:** Modify `forms/machine_forms.py` (add and remove). Create `api/forms.py`. Test: `tests/test_forms_api.py`.

Every endpoint is `@frappe.whitelist()` and calls `require_deployops_role()` first. Endpoints that act on a job call `job.check_permission("read")`.

**Interfaces (Plan 4 relies on these shapes):**
- `machine_forms(job: str, row: str) -> dict` (GET):
  ```
  {"job": str, "row": str, "item_code": str, "serial_no": str|None, "device_status": str,
   "job_status": str, "frozen": bool, "uses_forms": bool,
   "forms": [{"form": str, "title": str, "subtitle": str|None, "icon": str|None, "color": str|None,
              "required": bool, "origin": "Rule"|"Override", "status": "Not started"|"Draft"|"Submitted",
              "submission": str|None, "form_version": str|None, "flagged": bool,
              "can_start": bool, "can_remove": bool, "remove_needs_manager": bool}],
   "can_add": bool, "addable": [{"form": str, "title": str}]}
  ```
  - Only active rows are listed.
  - `submission` is the live one, or the cancelled one when status is Not started after a cancel.
  - `can_start`: the provider's `can_start` returns None, or a cancelled submission can be amended, and the user has the `c` letter.
  - `addable`: published, non-archived Forms with `context_doctype = "DeployOps Job"` that aren't active on the row. It is empty unless `can_add`.
- `start_machine_form(job: str, row: str, form: str) -> dict` (POST): `{"submission": str, "created": bool}`.
  - A live submission is returned with `created = False`.
  - When the row's submission is cancelled, it inserts an amendment: `frappe.get_doc({"doctype": "Form Submission", "amended_from": <cancelled>, "account", "form", "form_version", "context_doctype", "context_name", "context_row"})`, copied from the original, then `.insert()`.
  - Otherwise it calls `forms_core.submissions.start(form, "DeployOps Job", job, row)`.
- `override_machine_forms(job: str, row: str, add: list[str] | str | None = None, remove: list[str] | str | None = None, required: int = 0, reason: str | None = None) -> dict` (POST). Returns `machine_forms(job, row)`.
  - `add` and `remove` accept a JSON string or a list.
  - **Who:** `APPROVER_CAP` (`capacities` in `job_workflow`). Removing a required row also needs the `MANAGER` role (decision 7), plus a non-empty `reason`: "A reason is required to remove a required form."
  - **When:** the job status is not in `CLOSED` and not `Pending Review`, and the machine is not Completed or Cancelled.
  - **Add:** the form must be published, not Archived, and have `context_doctype = "DeployOps Job"`. A removed row is restored (`removed = 0`, origin Override, `required`). An active row is refused with "Form {0} is already planned for this machine." A new row is appended with origin Override.
  - **Remove:** the row must be active and have no live submission: "Cancel or discard form {0} first." It is set to `removed = 1`.
  - **All or nothing:** everything is checked before anything is applied.
  - **Log:** one `forms: add` / `forms: remove` entry per form. Save with `_save`.
- `discard_machine_form(submission: str, reason: str) -> None` (POST).
  - Needs the `x` letter on the job, a draft (docstatus 0), and a non-empty reason.
  - Logs `form: draft discarded` with `"<title> (<submission>): <reason>"`.
  - Clears the row's `submission` with `frappe.db.set_value`, then `frappe.delete_doc("Form Submission", submission, ignore_permissions=True)`.
- `cancel_machine_form(submission: str, reason: str) -> int` (POST).
  - Needs a non-empty reason.
  - Sets `frappe.flags.deployops_form_cancel = reason.strip()`, then `doc.check_permission("cancel")`, then `doc.cancel()`. The flag is cleared in a `finally`.
  - Returns `2`.

- [ ] **Step 1: Write the failing tests:**
  - `test_machine_forms_shape_and_statuses`: Not started, then Draft, then Submitted. Assert the exact keys above.
  - `test_start_returns_existing_draft`.
  - `test_restart_after_cancel_amends`: `amended_from` is set and the row points at the amendment.
  - `test_supervisor_adds_and_removes_optional_logged`: two Status Log rows with the actions and the form title.
  - `test_supervisor_cannot_remove_required`.
  - `test_manager_removes_required_with_reason_only`.
  - `test_remove_refused_with_live_submission`.
  - `test_override_survives_rule_resync`: a removed rule row stays removed and an override row stays after `resync_job_type`.
  - `test_override_all_or_nothing`: one bad form in `add` leaves the rows unchanged.
  - `test_technician_cannot_override`.
  - `test_discard_draft_manager_only_logged`.
  - `test_cancel_requires_reason_and_manager`.
  - `test_api_over_http`: `machine_forms` and `start_machine_form` through `frappe.tests.test_api.make_request` with `api_token(technician)`, on a committed fixture, following `TestWorkflowOverHttp`, including its tearDown.
- [ ] **Step 2:** Run `--module deployops.tests.test_forms_api`. Expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run it again. Expect PASS.
- [ ] **Step 5:** Commit `feat(v2): machine forms API`.

---

### Task 6: Cards, form job lists, Supervisor report and docs

**Files:** Modify `api/forms.py`, `docs/JOBS.md` (a "Machine forms (v2)" section) and `docs/PERMISSION_MATRIX.md` (the Form Rule row and the Form Submission letters). Test: `tests/test_forms_cards.py`.

**Interfaces:**
- `form_cards() -> list[dict]` (GET):
  ```
  [{"form": str, "title": str, "subtitle": str|None, "icon": str|None, "color": str|None,
    "job_types": [str], "open_jobs": int, "outstanding": int, "flagged": int,
    "attention": int, "waiting": bool}]
  ```
  - One card per published, non-archived Form with at least one active Form Rule, ordered by the lowest rule `sort_order`, then title.
  - **Counts** cover the user's visible open jobs (`frappe.get_list("DeployOps Job", filters={"status": ["not in", ["Completed", "Cancelled"]]}, pluck="name")`) that have an active row of the form on a machine that isn't Cancelled:
    - `outstanding`: jobs where such a row is required and not Submitted.
    - `flagged`: jobs where such a row is flagged.
    - `attention`: jobs counted in either.
    - `waiting = attention > 0`.
  - The counts come from one query that joins Job Device Form, Job Device and Form Submission over those job names.
- `form_jobs(form: str) -> dict` (GET):
  - Returns `{"card": <the form_cards entry>, "jobs": [{"name", "job_type", "customer_name", "address_display", "planned_date", "status", "machines": int, "outstanding": int, "flagged": int}]}`, ordered by `planned_date asc, modified desc`.
  - A form with no active rule raises `DoesNotExistError`.
- `report_rows(form: str, job: str | None = None, start: int = 0, page_length: int = 50) -> dict` (GET). This is the Supervisor report from §4.
  - **Who:** the user must hold SUPERVISOR, MANAGER or ADMINISTRATOR. Otherwise PermissionError.
  - **Form:** must have `context_doctype = "DeployOps Job"`. Otherwise DoesNotExistError.
  - **Paging:** `page_length` is capped at 200.
  - **Rows:**
    1. Get visible names with `frappe.get_list("Form Submission", filters={"form": form, "context_doctype": "DeployOps Job", "docstatus": ["in", [1, 2]], **({"context_name": job} if job else {})}, pluck="name", order_by="submitted_on desc", limit_start=start, limit_page_length=page_length)`. The provider's query conditions apply here.
    2. Read report rows with `frappe.get_all` on each part in `schema.report_doctypes(form)["parts"]`, filtered to those names, and merge them by `name`.
  - **Returns:** `{"status": <Form Report status or "Not built">, "columns": [{"fieldname", "label", "fieldtype"}], "rows": [dict], "total": int, "start": int, "page_length": int}`.
    - `columns` holds each part's non-hidden fields that aren't Table or layout fields: part 1's built-ins first, then the field columns in part order.
    - `total` is the length of the same permission-filtered `get_list` without paging.
  - Child tables are not included (v2.x, §11).

- [ ] **Step 1: Write the failing tests:**
  - `test_cards_from_rules_only`: a form with no active rule gives no card, and an archived form gives none.
  - `test_card_counts`: two jobs. One has A submitted on every machine, the other A missing and B flagged, which gives `open_jobs 2`, `outstanding 1`, `flagged 1`, `attention 1`.
  - `test_cards_follow_visibility`: the technician's counts cover only their assigned jobs, and a Supervisor without the category sees `open_jobs 0`.
  - `test_cancelled_machine_not_counted`.
  - `test_form_jobs_shape`.
  - `class TestReportRows(IntegrationTestCase)`:
    - In `setUpClass`, it publishes one job form with a unique key under `frappe.flags.forms_core_report_jobs = True`, calls `schema.sync_schema`, and commits.
    - In `tearDownClass`, it calls `schema.drop_report(form)`, deletes the rule, Form Version and Form rows with `frappe.db.delete`, and commits.
    - Each test sets the flag, builds its jobs and submissions, and rolls back in a cleanup.
    - `test_supervisor_sees_only_visible_jobs_rows`.
    - `test_job_filter`.
    - `test_technician_refused`.
    - `test_drafts_excluded_cancelled_included`.
    - `test_columns_skip_hidden_and_tables`.
- [ ] **Step 2:** Run `--module deployops.tests.test_forms_cards`. Expect FAIL.
- [ ] **Step 3:** Implement. Write the docs sections:
  - the rules and the union rule
  - when rows stop following the rules
  - overrides and who may make them
  - v1/v2 coexistence
  - outcomes
  - the API shapes, by reference to this plan's Task 5 and Task 6
- [ ] **Step 4:** Run the full suite: `bench --site deployops.local run-tests --app deployops`, then `ruff check deployops` and `ruff format --check deployops`. Expect all pass. Record the forms_core suite result from Task 1 again.
- [ ] **Step 5:** Commit `feat(v2): form cards and supervisor report`.
