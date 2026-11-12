# v2 Plan 2: report tables (implementation plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every published form a real, typed, read-only report DocType, built in the background from its submissions, so Desk reports, filters and exports work on answers.

**Architecture:** Submissions stay the source of truth. Each form gets a **Form Report** record that holds a permanent column map: (field id, field type) → column name, plus which table part the column lives in. A background job turns that map into generated DocTypes:
- one or more parts, one row per submission
- one child DocType per table field

Another job writes one row per submitted or cancelled submission. Columns are only ever added. Everything can be rebuilt from submissions at any time.

**Tech Stack:** Frappe v16 (Python 3.14), MariaDB; `frappe.enqueue`; `scheduler_events`.

**Spec:** `docs/superpowers/specs/2026-11-05-v2-form-builder-design.md` §4. This plan builds on Plan 1 (`docs/superpowers/plans/2026-11-05-v2-plan-1-forms-core-engine.md`).

**Not in this plan:** the Supervisor report screen filtered by job visibility (§4, "Who can see them"). It needs the job provider, so it moves to Plan 3. Analytics export and webhooks are v2.x.

## Global Constraints

- **Location and versions:**
  - Code lives in `forms_core`: `/home/kimbi/frappe/massarie_project/apps/forms_core`.
  - Branch: `task/v2-forms-core-reports`, created from `task/v2-forms-core-engine`.
  - Python 3.14, Frappe `>=16.50.0,<17`, ruff config as in the repo, tabs.
- **Generated DocTypes:**
  - `custom = 1`, module `Forms Core`. Name at most **61** characters.
  - Created and changed only through Frappe's DocType save, never hand-written DDL.
  - **Read-only for everyone.** Permissions are read, report and export only, for the roles in `forms_core_designer_roles` (fallback `System Manager`). No create, write, delete or import.
  - Rows are written only by the engine.
- **Naming:**
  - **Report name:** `"Form Report " + Title Case of the form key with "-" → " "`, e.g. key `cashmatic-installation` → **Form Report Cashmatic Installation**.
    - If that would be longer than 61 characters, cut the title part and append `" " + first 6 chars of sha1(key)`.
    - Set once on first publish and stored on Form Report. **Never renamed.**
  - **Part 2+ names:** `"<report name> P<n>"`.
  - **Child table names:** `"<report name> R<n>"` (n = 1, 2… in the order tables first appear).
  - Every name gets the same 61-character cut-and-hash rule.
- **Column names:**
  - The main column is the field `id`; a suffixed column is `id + suffix` (suffixes come from `FieldType.report_columns`).
  - When a field id appears with a **new type**, its columns get `_2`, `_3`… after the id and before any suffix (`f_8k2m_2`, `f_8k2m_2_signer`).
- **Built-in columns** on part 1:
  - `submission` (Link → Form Submission, unique)
  - `form_version` (Data), `status` (Select `Submitted\nCancelled`)
  - `context_doctype` (Data), `context_name` (Data), `context_row` (Data)
  - `account` (Data), `submitted_by` (Link → User), `submitted_on` (Datetime)
  - `submission_modified` (Datetime)
  
  Later parts carry only `submission`. Child report rows carry `row_id` (Data) plus their column fields. Every report row's `name` is the submission name.
- **Column budget per part:** at most **300** columns, and an estimated in-row size of at most **40,000 bytes**. Built-ins and Frappe's standard columns count toward the budget; Frappe's standard columns are estimated at 6 × 562.

  | Fieldtype | Estimated bytes |
  |---|---|
  | Data, Link | 562 |
  | Select | 562 |
  | Text | 40 |
  | Int | 4 |
  | Float, Currency | 10 |
  | Check | 4 |
  | Date | 3 |
  | Time | 6 |
  | Datetime | 8 |

- **Change rules (spec §4):**

  | Change | What happens |
  |---|---|
  | Field added | New column |
  | Label renamed | Column label changes only |
  | Field removed | Column stays, labelled `"<label> (removed in v<N>)"`, `hidden = 1` |
  | Field type changed | New column with the next `_n` |

  A column never changes type, moves part, or is dropped.
- **Rows:**
  - Only submissions with docstatus 1 (status Submitted) or 2 (status Cancelled) get rows. Drafts never do.
  - An amendment gets its own row; the cancelled original keeps its row with status Cancelled.
  - A row write is skipped when the stored `submission_modified` is newer than or equal to the submission's `modified`.
- **Jobs:**
  - Every enqueue goes through `forms_core.reports.jobs.enqueue(method: str, **kwargs)`. It runs inline when `frappe.flags.in_test` is set; otherwise it calls `frappe.enqueue(..., queue="long", job_id=..., deduplicate=True, enqueue_after_commit=True)`.
  - Job ids: `forms_core_report_schema::<form>`, `forms_core_report_row::<submission>`, `forms_core_report_rebuild::<form>`.
- **Failure:**
  - Any exception in a report job sets `Form Report.status = "Out of date"` and `last_error` (the first 500 chars), calls `frappe.log_error(title="forms_core report: <form>")`, and does not re-raise.
  - Submissions are never blocked by report failures.
  - A successful sync, write or rebuild sets status `OK` and `last_synced`.
- **Tests:**
  - `bench --site deployops.local run-tests --app forms_core`.
  - **DocType changes commit implicitly in MariaDB and are not rolled back.** Every test that creates report DocTypes must delete them in `tearDown` with `forms_core.reports.schema.drop_report(form)`, and use unique form keys.

## Review Focus

1. **Publish while a submission is being written:** a row job for version N arrives before the schema job has added version N's columns. The row job must sync the schema first, never fail on a missing column. → Task 4 `test_row_write_syncs_schema_first`.
2. **A long form key** (63 chars), or two keys whose long names cut to the same text: names stay at most 61 characters and stay unique. → Task 2 `test_long_keys_get_unique_short_names`.
3. **A technician (Website User) calling `/api/resource/Form Report …`** or `frappe.get_list` on a report DocType: refused. → Task 3 `test_report_doctype_not_readable_by_non_designer`.
4. **One bad submission** (a value the column type rejects) during a rebuild: that row fails and is logged, other rows are still written, and status becomes Out of date. → Task 6 `test_rebuild_continues_past_bad_row`.
5. **A cancelled submission later amended:** the original row shows Cancelled, the amendment has its own Submitted row, and nothing is double-counted by the nightly check. → Task 6 `test_cancel_then_amend_rows`.

---

## File structure (inside `forms_core/forms_core/`)

```
field_types/*.py            # + report_values(value, field) on every type
reports/__init__.py
reports/naming.py           # report_name(key), part_name, child_name, short_name
reports/planner.py          # plan_columns(versions, existing) -> list[Column] (pure)
reports/schema.py           # sync_schema(form), drop_report(form)
reports/rows.py             # write_row(submission), row_values(doc)
reports/jobs.py             # enqueue(), on_publish, on_submit/on_cancel hooks
reports/rebuild.py          # rebuild(form), check_all()
forms_core/doctype/form_report/, form_report_column/   # map + status
tests/test_report_values.py, test_report_planner.py, test_report_schema.py,
      test_report_rows.py, test_report_rebuild.py
```

---

### Task 1: `report_values` on every field type

**Files:** Modify `forms_core/field_types/base.py` and each type module. Test: `forms_core/tests/test_report_values.py`.

**Interfaces:**
- Produces: `FieldType.report_values(self, value, field: dict) -> dict[str, Any]`, keyed by the same suffixes `report_columns` returns.
  - The base class returns `{}`.
  - A `None` or empty value gives `None` for every suffix, except Int counts, which give `0`.

  | Type | `report_values` |
  |---|---|
  | text, long_text, yes_no | `{"": value}` |
  | number, currency | `{"": value}` |
  | checkbox | `{"": 1 if value else 0}` |
  | date, time, datetime | `{"": the stored ISO string}` |
  | choice | `{"": value if str else None}`, plus `"_other": value["other"]` when allow_other |
  | multi_check | `{"": ", ".join(selected + ([other] if other else []))}` |
  | photos, files | `{"": len(value)}` |
  | signature | `{"_signer": value["signer"], "_signed_at": value["signed_at"]}` |
  | table, info | `{}` (tables are written by Task 5 through child tables) |

- [ ] **Step 1:** Write failing tests:
  - `test_<type>_report_values` for each of the 16 types, using the exact outputs in the table above.
  - `test_report_values_keys_match_report_columns`: for every type with a sample config, the key set of `report_values(sample)` equals `{c["suffix"] for c in report_columns(field)}`.
- [ ] **Step 2:** Run `bench --site deployops.local run-tests --app forms_core --module forms_core.tests.test_report_values`. Expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run again. Expect PASS.
- [ ] **Step 5:** Commit `feat: report values for field types`.

---

### Task 2: Naming and the column planner (pure functions)

**Files:** Create `reports/__init__.py`, `reports/naming.py`, `reports/planner.py`. Test: `tests/test_report_planner.py`.

**Interfaces:**
- Produces in `naming.py`:
  - `short_name(base: str, key: str) -> str`: the 61-character rule from the Global Constraints.
  - `report_name(key: str) -> str`.
  - `part_name(report: str, n: int) -> str` (n ≥ 2).
  - `child_name(report: str, n: int) -> str`.
- Produces in `planner.py`:
  - `Column`, a dataclass with: `field_id: str`, `field_type: str`, `generation: int` (1 = first type, 2 = `_2`…), `suffix: str`, `fieldname: str`, `fieldtype: str`, `label: str`, `part: int`, `table_field: str | None` (set for a table field's columns, which go to that table's child report), `removed_in: int | None`.
  - `plan_columns(versions: list[tuple[int, dict]], existing: list[Column]) -> list[Column]`. `versions` is (version_no, definition) in ascending order; `existing` is the stored map. It returns the full new map:
    - **Every existing column is kept,** with the same fieldname and part.
    - New (field id, type) pairs get new columns. The generation is the next unused one for that id.
    - Labels come from the **latest** version that has the field.
    - `removed_in` = the first version number after the last version that contains the (id, type). It is None if the latest version contains it.
    - Top-level value fields → part columns. Table columns → that table's child columns.
    - **Part assignment:** new part columns go into the lowest part whose budget still fits, otherwise a new part. Child tables are budgeted separately, and each has only one part. If a child table would exceed the budget, raise `ValueError("Table <label> has too many columns for a report")`.
  - `part_budget_ok(columns: list[Column]) -> bool`: the budget check from the Global Constraints.

- [ ] **Step 1:** Write failing tests:
  - `test_report_name_title_cases_key` (`cashmatic-installation` → `Form Report Cashmatic Installation`).
  - `test_long_keys_get_unique_short_names`: two 63-character keys sharing their first 50 characters give names of at most 61 characters that differ.
  - `test_part_and_child_names`.
  - `test_plan_first_version`: columns for text, choice with other, and signature have the right fieldnames and suffixes.
  - `test_plan_add_field_keeps_existing`.
  - `test_plan_label_rename_changes_label_only`.
  - `test_plan_removed_field_marked`: `removed_in == 3` when the field is in v1 and v2 but not v3.
  - `test_plan_type_change_new_generation` (`f_x` text in v1, number in v2 gives `f_x` and `f_x_2`).
  - `test_plan_existing_never_moves_part`.
  - `test_plan_splits_into_part_2` (e.g. 80 text fields at 562 bytes each go past 40,000 bytes).
  - `test_plan_table_columns_go_to_child`.
  - `test_plan_child_over_budget_raises`.
- [ ] **Step 2:** Run `--module forms_core.tests.test_report_planner`. Expect FAIL.
- [ ] **Step 3:** Implement. Use `field_types.get_type(t).report_columns(field)` for each field's columns.
- [ ] **Step 4:** Run again. Expect PASS.
- [ ] **Step 5:** Commit `feat: report naming and column planner`.

---

### Task 3: Form Report DocTypes and schema sync

**Files:**
- Create the DocTypes:
  - **Form Report** (fields: `form` Link Form reqd unique, `report_doctype` Data read-only, `status` Select `OK\nOut of date\nNot built` default `Not built`, `last_error` Small Text, `last_synced` Datetime, `columns` Table → Form Report Column; autoname `field:form`; perms System Manager read only).
  - **Form Report Column** (child; one Data/Int field per `Column` attribute).
- Create: `reports/schema.py`.
- Test: `tests/test_report_schema.py`.

**Interfaces:**
- Consumes: `plan_columns`, `Column`, the naming functions (Task 2).
- Produces:
  - `schema.sync_schema(form: str) -> str`: returns the part-1 DocType name.
    1. Lock the Form Report row (create it on first call).
    2. Load all Form Versions for the form in order, then run `plan_columns` against the stored map.
    3. Save the map.
    4. For each part and child, create or update its DocType through a `frappe.get_doc("DocType")` save. It holds the built-in columns (Global Constraints), one field per column (`hidden` when `removed_in`, label suffixed `(removed in v<N>)`), and on part 1 one `Table` field per child DocType, labelled with the table field's label.
    5. Set permissions from the designer roles.
    6. Set status OK and `last_synced`.
    
    Calling it again with no new versions changes nothing.
  - `schema.drop_report(form: str) -> None`: deletes every generated DocType (`frappe.delete_doc("DocType", name, force=True)`) and the Form Report. Used by tests, and by a future form deletion.
  - `schema.report_doctypes(form: str) -> dict`: `{"parts": [names], "children": {table_field_id: name}}`.

- [ ] **Step 1:** Write failing tests. Each one publishes a form built from Plan 1 test utils, then calls `sync_schema`; tearDown calls `drop_report`.
  - `test_sync_creates_doctype_with_builtins_and_columns` (check `frappe.get_meta(name)` for `submission` unique and one field per column).
  - `test_sync_is_idempotent` (the DocType's modified timestamp is unchanged on the second call).
  - `test_new_version_adds_column`.
  - `test_removed_field_hidden_and_labelled`.
  - `test_type_change_adds_generation_column`.
  - `test_child_doctype_for_table_field` (istable 1, plus the Table field on part 1).
  - `test_part_2_created_when_over_budget`.
  - `test_report_doctype_not_readable_by_non_designer`: a Website User gets False from `frappe.has_permission(name, "read")`, and `frappe.get_list(name)` raises PermissionError.
  - `test_report_doctype_has_no_write_perms`: the DocPerm rows have write = create = delete = import = 0.
- [ ] **Step 2:** Run `--module forms_core.tests.test_report_schema`. Expect FAIL.
- [ ] **Step 3:** Implement. Run `bench --site deployops.local migrate` for the two new DocTypes.
- [ ] **Step 4:** Run again. Expect PASS.
- [ ] **Step 5:** Commit `feat: generated report doctypes`.

---

### Task 4: Writing rows

**Files:** Create `reports/rows.py`. Test: `tests/test_report_rows.py`.

**Interfaces:**
- Consumes: `sync_schema`, `report_doctypes`, the stored map (Task 3); `report_values` (Task 1); `submissions.version_definition(version)`, `submissions._as_dict` (Plan 1).
- Produces:
  - `rows.row_values(doc) -> dict`: `{part_doctype: {fieldname: value}, ...}` plus `{"children": {child_doctype: [ {row_id, fieldname: value} ]}}`.
    - Each answer maps through the map entry for (field id, the field's type **in that submission's version**).
    - Answers whose field is missing from the version are skipped.
  - `rows.write_row(submission: str) -> bool`: returns True when written, False when skipped.
    - Skip when docstatus is 0, or the stored `submission_modified` ≥ the submission's modified.
    - If the submission's version is not yet in the map, call `sync_schema` first.
    - Writes go directly to the database (`frappe.get_doc({...}).db_insert()` / `db_update()` with `ignore_permissions`), with `name` = submission.
    - Child rows are deleted and rewritten for that submission.
    - Sets status from docstatus (1 → Submitted, 2 → Cancelled).

- [ ] **Step 1:** Write failing tests. Each submits through Plan 1's API; tearDown calls `drop_report`.
  - `test_submitted_row_written_with_builtins` (submission, form_version, status Submitted, submitted_by, context fields).
  - `test_values_land_in_typed_columns` (text, number, choice + other, multi_check joined, photos count, signature signer/signed_at).
  - `test_draft_gets_no_row`.
  - `test_cancel_sets_status_cancelled`.
  - `test_older_write_skipped` (set the stored `submission_modified` into the future; `write_row` returns False).
  - `test_row_write_syncs_schema_first` (publish v2, submit on v2 without calling sync_schema; `write_row` succeeds and the v2 column exists).
  - `test_type_changed_field_uses_its_generation_column`.
  - `test_table_rows_written_to_child` (two answer rows give two child rows with row_id).
  - `test_part_2_values_written` (a form over budget).
- [ ] **Step 2:** Run `--module forms_core.tests.test_report_rows`. Expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run again. Expect PASS.
- [ ] **Step 5:** Commit `feat: write report rows`.

---

### Task 5: Background jobs and failure handling

**Files:**
- Create: `reports/jobs.py`.
- Modify:
  - `versions.publish` (enqueue the schema sync after the version insert).
  - The Form Submission controller `on_submit` / `on_cancel` (enqueue the row write after the provider calls).
  - `hooks.py`.
- Test: `tests/test_report_rows.py` (class `TestReportJobs`).

**Interfaces:**
- Produces:
  - `jobs.enqueue(method: str, job_id: str, **kwargs) -> None` (Global Constraints).
  - `jobs.run_schema(form: str)` and `jobs.run_row(submission: str)`: the job entry points. Each wraps its work in the failure handling from the Global Constraints, using `schema.sync_schema` and `rows.write_row`. Task 6 adds `jobs.run_rebuild(form: str)` the same way.
- **Rules:**
  - `publish` enqueues `run_schema`.
  - Submit and cancel enqueue `run_row`.
  - A failure never raises into publish, submit or cancel.

- [ ] **Step 1:** Write failing tests:
  - `test_publish_builds_report` (status OK and the DocType exists right after publish in tests).
  - `test_submit_writes_row`.
  - `test_cancel_updates_row`.
  - `test_failure_marks_out_of_date_and_does_not_block`: patch `rows.write_row` to raise. Submit still succeeds, Form Report.status is `Out of date`, `last_error` is set, and an Error Log exists.
  - `test_enqueue_uses_job_id_dedup`: patch `frappe.enqueue` with `frappe.flags.in_test` False and assert `job_id`, `deduplicate=True`, `queue="long"` and `enqueue_after_commit=True`.
- [ ] **Step 2:** Run. Expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run again. Expect PASS.
- [ ] **Step 5:** Commit `feat: report background jobs`.

---

### Task 6: Rebuild, nightly check and API

**Files:**
- Create: `reports/rebuild.py`.
- Modify: `api.py`, `hooks.py` (`scheduler_events = {"daily": ["forms_core.reports.rebuild.check_all"]}`), `README.md` (a Reports section).
- Test: `tests/test_report_rebuild.py`.

**Interfaces:**
- Produces:
  - `rebuild.rebuild(form: str) -> dict`, returning `{"written": int, "failed": [submission names]}`.
    1. `sync_schema`.
    2. Delete every row in every part and child report DocType of the form.
    3. Write every submission with docstatus 1 or 2, in batches of 500, each inside its own savepoint. A failing submission is logged and listed, and the rest continue.
    4. Status: OK when nothing failed, otherwise Out of date.
  - `rebuild.check_all() -> None`. For every Form Report:
    - Write any submitted or cancelled submission whose row is missing or whose `submission_modified` is older.
    - Delete report rows whose submission no longer exists.
    - It never runs a full rebuild.
  - `jobs.run_rebuild(form: str)`: the rebuild job entry point, with the same failure handling as Task 5.
  - `api.rebuild_report(form: str)` (POST; designer): enqueues `run_rebuild` and returns `{"queued": True}`.
  - `api.report_status(form: str)` (designer): returns `{"report_doctype", "status", "last_error", "last_synced", "parts": [...], "children": {...}}`.

- [ ] **Step 1:** Write failing tests:
  - `test_rebuild_matches_submissions` (3 submitted + 1 cancelled + 1 draft gives 4 rows).
  - `test_rebuild_continues_past_bad_row`: patch `rows.row_values` to raise for one submission. `failed == [that name]`, the other rows are written, status is Out of date.
  - `test_check_all_fills_missing_row` (delete one row directly; `check_all` restores it).
  - `test_check_all_removes_orphan_row`.
  - `test_cancel_then_amend_rows` (the original is Cancelled, the amendment Submitted, 2 rows; `check_all` adds nothing).
  - `test_rebuild_report_requires_designer`.
  - `test_report_status_shape`.
  - `test_daily_hook_registered` (`frappe.get_hooks("scheduler_events")["daily"]` contains `check_all`).
- [ ] **Step 2:** Run `--module forms_core.tests.test_report_rebuild`. Expect FAIL.
- [ ] **Step 3:** Implement. Add the README section covering naming, add-only columns, status, rebuild and the nightly check.
- [ ] **Step 4:** Run the full suite and ruff. Expect all pass.
- [ ] **Step 5:** Commit `feat: report rebuild, nightly check and API`.
