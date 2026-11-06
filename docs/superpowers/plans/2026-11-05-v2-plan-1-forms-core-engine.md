# v2 Plan 1: `forms_core` engine foundation (implementation plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A new Frappe app, `forms_core`, that stores forms as locked versions, accepts and checks submissions through a whitelisted API, and connects to the outside world only through context providers. It has no UI yet.

**Architecture:** Forms are data: a `Form` holds a draft definition (JSON), each publish writes a `Form Version` that can't be changed, and a `Form Submission` holds answers keyed by permanent field IDs. Field types are plug-ins registered through a hook. Conditions use a small JSON rules language with identical Python and TypeScript readers, both proven by one shared case file.

**Tech Stack:** Frappe v16 (Python 3.14), MariaDB, `IntegrationTestCase`; TypeScript + vitest for the browser rules reader.

**Spec:** `docs/superpowers/specs/2026-11-05-v2-form-builder-design.md` (§3, §5, §7.1, §9). The executor reads both documents.

## The v2.0 plan series

This is plan 1 of 7. Each plan ships working, tested software and gets its own plan document when its turn comes.

| Plan | Delivers | Spec |
|---|---|---|
| **1. Engine foundation (this plan)** | App, data model, rules, server field types, publish/versions, submissions, context-provider interface, export/import | §3, §5, §7.1, §9 |
| 2. Report tables | Generated report DocTypes, background sync, Part 2 split, rebuild, nightly check | §4 |
| 3. DeployOps job connection | Job provider, Form Rule, Job Device Form, override, blocking, cards | §7.2–7.3 |
| 4. Technician screen | Generic form renderer from version JSON, front-end field plug-ins, autosave | §8 |
| 5. Builder | Forms list, three-panel builder, conditions editor, preview, publish flow, versions | §6 |
| 6. PDF reports | Internal and customer copies from any version | §8 |
| 7. The five v1 forms | Rebuilt as templates shipped as files, loaded on migrate, accepted end to end | §1, §10 |

## Global Constraints

- **Versions and style:**
  - Python `>=3.14,<3.15`; Frappe `>=16.50.0,<17.0.0`, copied from `deployops/pyproject.toml`.
  - ruff `line-length = 110`, tabs, same lint selection as DeployOps.
- **Independence:** `forms_core` never imports `deployops`. DeployOps-specific behaviour arrives only through hooks.
- **Account:** every Form, Form Version and Form Submission has an `account` (Link → Form Account). Install creates one account, `Default`, and it is the default value.
- **Patterns:**

  | Item | Pattern |
  |---|---|
  | Section `id` | `^s_[a-z0-9]{4,12}$` |
  | Field `id` (including table column IDs) | `^f_[a-z0-9]{4,12}$` |
  | Table row `_row` | `^r_[a-z0-9]{1,12}$` |
  | Field `key` | `^[a-z][a-z0-9_]{0,62}$` |
  | Form `key` | `^[a-z][a-z0-9-]{0,62}$` |

- **Limits:** definition `schema` is `1`. Answers JSON is at most **1,000,000 bytes** (UTF-8, as stored). Rule nesting is at most **depth 4**.
- **Secrets check:** copied verbatim from v1, `deployops/checklists/form.py:61`:
  `re.compile(r"\b(password|passwd|pwd|mot de passe|otp|pin|pairing code|code d'appairage)\b\s*[:=]\s*\S", re.IGNORECASE)`
- **Designers:** designer rights come from the hook `forms_core_designer_roles` (a list of role names). With no hook, it is `["System Manager"]`. DeployOps adds `DeployOps Manager` and `DeployOps Administrator` in Plan 3.
- **Errors:** each error carries `{"field": <id or null>, "row": <_row or null>, "message": str}` and is raised as `forms_core.errors.FormValidationError(errors: list[dict])`.
- **Tests:** run with `bench --site deployops.local run-tests --app forms_core`, using `frappe.tests.IntegrationTestCase`. JS tests run with `yarn test` in `forms_core/js`.

## Review Focus

1. **Direct API answers:** an answer sent for a field ID that isn't in the version, or of the wrong shape (text for a number, a table row with no `_row`), is refused with a field-linked error, never stored. → Task 7 `test_unknown_field_refused`, `test_wrong_shape_refused`.
2. **Hidden answers are removed:** an answer saved while its field was visible is removed on the next save once a rule hides the field, and isn't required on submit. → Task 7 `test_hidden_answer_removed_on_save`.
3. **Two publishes at once:** two publishes of the same form at the same moment must not create two versions with the same number. The unique index on (form, version_no) makes the second fail cleanly. → Task 5 `test_duplicate_version_no_refused`.
4. **Secrets inside table cells** and long Unicode text: refused or stored intact respectively. → Task 7 `test_secret_in_table_cell_refused`, `test_unicode_text_kept`.
5. **Deleting in use:** deleting a Form that has versions or submissions, or a published Form Version, is refused. → Task 4 `test_form_with_versions_not_deletable`, Task 5 `test_version_not_deletable`.

---

## File structure (new app at `/home/kimbi/frappe/massarie_project/apps/forms_core`)

```
forms_core/
  pyproject.toml, README.md, license.txt
  forms_core/
    hooks.py                      # after_install, designer roles default, field types, providers
    install.py                    # Default account
    errors.py                     # FormValidationError
    secrets.py                    # looks_like_secret
    ids.py                        # id/key patterns, new_id()
    rules.py                      # evaluate(rule, answers), references(rule), check_rule(rule)
    rules_cases.json              # shared cases (Python + TS)
    field_types/
      __init__.py                 # registry: get_type(name), all_types()
      base.py                     # FieldType base class
      basic.py                    # text, long_text, number, currency, checkbox, yes_no, date, time, datetime, info
      choice.py                   # choice, multi_check
      files.py                    # photos, files
      signature.py                # signature
      table.py                    # table (incl. fixed rows)
    definition.py                 # validate_definition(definition, previous_ids) -> None
    context.py                    # ContextProvider base, get_provider(doctype)
    permissions.py                # is_designer(user), submission permission hooks
    versions.py                   # publish(), restore_as_draft(), compare()
    submissions.py                # start(), save_answers(), submit checks, upgrade_draft()
    transfer.py                   # export_form(), import_form()
    api.py                        # whitelisted endpoints (§9)
    forms_core/doctype/{form_account,form,form_version,form_submission}/
    tests/ test_rules.py, test_field_types.py, test_definition.py, test_form.py,
           test_versions.py, test_submissions.py, test_context.py, test_transfer.py, utils.py
  js/
    package.json, tsconfig.json
    src/rules.ts, src/rules.test.ts
```

---

### Task 1: Create the app and install the Default account

**Files:**
- Create: the app via `bench new-app forms_core` (title "Forms Core", publisher "Nexgen Business Solutions", email `support@nxgensolutions.com`, licence MIT), then edit `pyproject.toml` to match the Global Constraints.
- Create: `forms_core/install.py`, `forms_core/errors.py`, `forms_core/ids.py`, `forms_core/secrets.py`, the `Form Account` DocType (fields `title` Data reqd unique, `status` Select `Active\nSuspended` default Active; named by `title`).
- Modify: `forms_core/hooks.py` (`after_install = "forms_core.install.after_install"`, `after_migrate = "forms_core.install.after_install"`).
- Test: `forms_core/tests/test_install.py`, `forms_core/tests/test_ids.py`.

**Interfaces:**
- Produces:
  - `install.DEFAULT_ACCOUNT = "Default"`; `install.after_install() -> None`, which is idempotent.
  - `ids.new_id(prefix: str) -> str` returns e.g. `f_8k2m9q` (prefix + `_` + 6 lowercase base36 chars).
  - `ids.FIELD_ID`, `ids.SECTION_ID`, `ids.ROW_ID`, `ids.FIELD_KEY`, `ids.FORM_KEY`: compiled patterns from the Global Constraints.
  - `secrets.looks_like_secret(value) -> bool`.
  - `errors.FormValidationError(errors: list[dict])`, a subclass of `frappe.ValidationError` with an `.errors` attribute.

- [ ] **Step 1:** Run `bench new-app forms_core` in `/home/kimbi/frappe/massarie_project`, then `bench --site deployops.local install-app forms_core`. Expect "Installing forms_core…" with no error.
- [ ] **Step 2: Write failing tests:**
  - `test_default_account_exists`: `frappe.db.exists("Form Account", "Default")`.
  - `test_after_install_is_idempotent`: call it twice; the count of `Form Account` named Default is 1.
  - `test_new_id_matches_pattern`: `ids.FIELD_ID.match(new_id("f"))` and two calls differ.
  - `test_secret_detected`: true for `"PIN: 1234"` and `"mot de passe = x"`, false for `"Pinpoint"`.
- [ ] **Step 3:** Run `bench --site deployops.local run-tests --app forms_core`. Expect FAIL (missing modules).
- [ ] **Step 4:** Implement the files listed above.
- [ ] **Step 5:** Run the tests again. Expect PASS.
- [ ] **Step 6:** In `forms_core`, run `git init`, then commit `feat: forms_core app with default account`. The GitHub repository is created by the owner; don't push until it exists.

---

### Task 2: Rules language (Python, TypeScript, shared cases)

**Files:**
- Create: `forms_core/rules.py`, `forms_core/rules_cases.json`, `js/package.json` (vitest only, `"test": "vitest run"`), `js/tsconfig.json`, `js/src/rules.ts`, `js/src/rules.test.ts`.
- Test: `forms_core/tests/test_rules.py`.

**Interfaces:**
- Produces (Python):
  - `rules.evaluate(rule: dict | None, answers: dict) -> bool`. `None` means always true.
  - `rules.references(rule: dict) -> set[str]`: every field ID the rule reads.
  - `rules.check_rule(rule: dict) -> list[str]`: shape problems (unknown op, depth > 4, missing value). An empty list means valid.
- Produces (TS): `evaluate(rule: Rule | null, answers: Answers): boolean`, `references(rule: Rule): Set<string>`, with the same semantics.
- **Format** (spec §5.2):
  - A condition is `{"field", "op", "value"}`, where op is one of `eq ne in not_in gt gte lt lte empty not_empty contains`.
  - Groups are `{"all": [...]}`, `{"any": [...]}`, `{"not": rule}`.
- **Semantics the case file must pin:**
  - A missing answer is empty.
  - `gt/gte/lt/lte` on empty or non-numeric values give false.
  - `contains` works on lists (multi_check answers are `{"selected": [...], "other": str|null}`; it checks `selected`).
  - `eq` compares strings as-is (case-sensitive).
  - `empty` is true for `None`, `""`, `[]` and a multi_check with nothing selected and no other.
  - `all: []` is true and `any: []` is false.

- [ ] **Step 1: Write `rules_cases.json`:** a list of `{"name", "rule", "answers", "expected"}`. It needs at least one case per operator, per group type, each semantic above, and nesting at depth 4. Aim for about 30 cases.
- [ ] **Step 2: Write failing tests:**
  - `test_shared_cases` loops over the file, asserting `evaluate(case.rule, case.answers) == case.expected` with the case name in the message.
  - `test_depth_5_rejected`: `check_rule` of a depth-5 rule is non-empty.
  - `test_unknown_op_rejected`.
  - `test_references_collects_nested_fields`.
  - In vitest, `rules.test.ts` imports `../../forms_core/rules_cases.json` and runs the same loop.
- [ ] **Step 3:** Run both test suites. Expect FAIL.
- [ ] **Step 4:** Implement `rules.py` and `rules.ts`. Each is a recursive evaluator with no `eval` or `exec` and no access to anything outside `answers`.
- [ ] **Step 5:** Run both suites. Expect PASS.
- [ ] **Step 6:** Commit `feat: rules language with shared cases`.

---

### Task 3: Field-type plug-ins (server)

**Files:**
- Create: `forms_core/field_types/{__init__,base,basic,choice,files,signature,table}.py`.
- Modify: `hooks.py` to add `forms_core_field_types = ["forms_core.field_types.basic", "forms_core.field_types.choice", "forms_core.field_types.files", "forms_core.field_types.signature", "forms_core.field_types.table"]`.
- Test: `forms_core/tests/test_field_types.py`.

**Interfaces:**
- Produces: `base.FieldType`, a class with:
  - `name: ClassVar[str]` and `has_value: ClassVar[bool] = True` (`info` sets False)
  - `validate_config(self, config: dict) -> list[str]`
  - `normalize(self, value, field: dict) -> Any`: shapes the value or raises `ValueError(message)`
  - `is_empty(self, value) -> bool`
  - `validate(self, value, field: dict) -> list[dict]`: submit-time checks; errors are `{"field","row","message"}`
  - `text_values(self, value) -> list[str]`: the strings the secrets check reads
  - `report_columns(self, field: dict) -> list[dict]`: `{"suffix": str, "fieldtype": str, "label": str}`, used by Plan 2
  - `to_text(self, value, field: dict) -> str`: used by Plan 6
- Produces: `field_types.get_type(name: str) -> FieldType` (raises `KeyError` for an unknown type) and `all_types() -> dict[str, FieldType]`. Modules come from the hook; each module lists its classes in `TYPES = [...]`.
- **Value shapes and config per type** (spec §5.1):

  | Type | Value | Config |
  |---|---|---|
  | `text` | str | `max_length` (default 140) |
  | `long_text` | str | — |
  | `number` | int or float | `decimal: bool`, `min`, `max` |
  | `currency` | float | `currency` |
  | `checkbox` | bool | `must_tick: bool` |
  | `yes_no` | `"Yes"` or `"No"` | — |
  | `date`, `time`, `datetime` | ISO strings | — |
  | `info` | no value | `text` |
  | `choice` | str in options, or `{"other": str}` | `options: list[str]` (non-empty, unique), `display: "dropdown"\|"buttons"`, `allow_other: bool` |
  | `multi_check` | `{"selected": [...], "other": str\|null}` | `options`, `min_selected: int` (default 0), `allow_other` (other text counts as one selected) |
  | `photos`, `files` | list of `{"file": "/private/files/…", "caption": str\|null}` | `min`, `max`, `captions: bool`, `extensions: list[str]` (files only) |
  | `signature` | `{"file", "signer", "signed_at", "captured_by"}` | `signer_from: <field id> \| "context:technician"` |
  | `table` | list of rows `{"_row": …, <column id>: value}` | `columns: list[field]` (only text, long_text, number, checkbox, yes_no, choice, date, time), `min_rows: int`, `fixed_rows: {"column": <id>, "labels": [str]}\|null` |

- **Rules:**
  - `photos`, `files` and `signature` accept only URLs starting with `/private/files/`. The check that the file is attached to the submission is done in Task 7.
  - `table` normalizes each cell through the column's type.
  - Fixed rows: row count and labels must match `labels` exactly.

- [ ] **Step 1: Write failing tests,** one test class per module.
  - **Each type:** `test_<type>_normalize_accepts`, `test_<type>_normalize_rejects` (one wrong shape each), and `test_<type>_is_empty`.
  - **Specific cases:**
    - `test_number_outside_range`: min 0, max 10, value 11 gives one error.
    - `test_multi_check_other_counts`: `min_selected=1`, `{"selected": [], "other": "x"}` gives no errors.
    - `test_photos_min_count`: `min=3` with two photos gives one error.
    - `test_photos_public_url_rejected`: `/files/x.png` raises ValueError.
    - `test_table_fixed_rows_labels_locked`.
    - `test_table_cell_normalized_by_column_type`.
    - `test_choice_options_must_be_unique` (`validate_config`).
    - `test_unknown_type_raises`.
    - `test_hook_registers_all_v2_types` (the 16 type names above are all present).
- [ ] **Step 2:** Run the tests. Expect FAIL.
- [ ] **Step 3:** Implement `base.py`, then one module at a time.
- [ ] **Step 4:** Run the tests. Expect PASS.
- [ ] **Step 5:** Commit `feat: server field-type plug-ins`.

---

### Task 4: Definition checks and the Form DocType

**Files:**
- Create: `forms_core/definition.py`, `forms_core/permissions.py`, and the `Form` DocType (spec §3.1: `account`, `title` reqd, `key` reqd unique, `status` Select `Draft\nPublished\nArchived` default Draft, `draft_definition` JSON, `current_version` Link → Form Version read-only, `icon` Data, `color` Data, `subtitle` Data; autoname `hash`).
- Modify: `hooks.py` to add `forms_core_designer_roles` reading in `permissions.py`.
- Test: `forms_core/tests/test_definition.py`, `forms_core/tests/test_form.py`.

**Interfaces:**
- Produces: `definition.validate_definition(definition: dict, previous_ids: dict[str, str] | None = None) -> None` (`previous_ids` maps every field ID from earlier versions to its type), which raises `FormValidationError` with all problems at once. It checks:
  - `schema == 1`, and sections is a non-empty list.
  - IDs match their patterns and are unique across sections, fields and table columns.
  - Keys are unique within the definition.
  - **No ID from `previous_ids` is reused for a different type:** a field ID that existed before may come back only as the same field. An ID retired from a previous version may not be created again under another type. (Spec §3.2: never reused; Plan 2 relies on this for type changes.)
  - Each `type` is registered, and `validate_config` is clean.
  - `show`, `required_when` and outcome `when` pass `check_rule`, and refer only to fields **earlier in the form** (section order, then field order). A section's `show` may refer only to fields in earlier sections.
  - `fill_from.value` and outcome `effect` are checked later by the provider (Task 6). Here they need only be non-empty strings.
- Produces: `definition.field_index(definition) -> dict[str, dict]` (id → field, including table columns, each tagged with `section`) and `definition.ordered_fields(definition) -> list[dict]`.
- Produces: `permissions.is_designer(user: str | None = None) -> bool` and `permissions.require_designer() -> None` (raises `frappe.PermissionError`).
- **Form controller:**
  - `on_trash` refuses if any Form Version or Form Submission links to it (Review Focus 5).
  - `validate` checks `key` against `FORM_KEY`.
  - `draft_definition` is **not** checked on save (drafts may be incomplete); it's checked at publish.
  - DocType permissions: read/write/create for System Manager. Designers act through the API in Task 5.

- [ ] **Step 1: Write failing tests:**
  - `test_valid_definition_passes` (a fixture with 2 sections, one table, one rule).
  - `test_duplicate_id_reported_with_field`.
  - `test_duplicate_key_reported`.
  - `test_rule_referencing_later_field_refused`.
  - `test_rule_referencing_missing_field_refused`.
  - `test_retired_id_reused_as_new_type_refused`.
  - `test_unknown_type_refused`.
  - `test_all_errors_reported_together` (three problems give three errors).
  - `test_form_key_pattern`.
  - `test_form_with_versions_not_deletable`.
  - `test_is_designer_uses_hook` (patch `frappe.get_hooks` to return `["Test Designer"]`).

  Put definition fixtures in `tests/utils.py` as `simple_definition()`, built with `new_id`.
- [ ] **Step 2:** Run the tests. Expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests. Expect PASS.
- [ ] **Step 5:** Commit `feat: form definition checks and Form doctype`.

---

### Task 5: Form Version and publishing

**Files:**
- Create: the `Form Version` DocType (spec §3.1: `form` Link reqd, `account`, `version_no` Int, `definition` JSON, `schema` Int, `definition_hash` Data, `published_by` Link User, `published_on` Datetime, `change_note` Small Text; autoname `format:{form}-v{version_no}`; unique index on `(form, version_no)` added in the controller's `on_doctype_update`).
- Create: `forms_core/versions.py`.
- Modify: `forms_core/api.py` (builder calls).
- Test: `forms_core/tests/test_versions.py`.

**Interfaces:**
- Consumes: `validate_definition`, `field_index` (Task 4); `require_designer` (Task 4).
- Produces:
  - `versions.publish(form: str, change_note: str | None = None) -> str`: returns the new Form Version name.
    1. Load the Form with `for_update=True`.
    2. Gather `previous_ids` as id → type from every earlier version.
    3. Run `validate_definition`.
    4. Hash a canonical dump (`json.dumps(sort_keys=True, separators=(",", ":"))`, sha256). If it equals the current version's hash, raise `FormValidationError([{"field": None, "row": None, "message": "Nothing changed since v<n>."}])`.
    5. Insert version n+1 and set `current_version`; status becomes Published.
  - `versions.restore_as_draft(version: str) -> None`: copies the definition into `draft_definition`.
  - `versions.compare(a: str, b: str) -> dict`: `{"added": [ids], "removed": [ids], "changed": [ids]}` by field ID.
  - `versions.drafts_on_older(form: str) -> dict[str, int]`: version name → count of draft submissions. It returns `{}` until Task 7 exists, and is used by the publish summary in Plan 5.
- **Form Version controller:**
  - `validate` refuses any change to an existing record (`if not self.is_new(): frappe.throw`).
  - `on_trash` always refuses.
- **API:** `api.list_forms()`, `api.get_form(form)`, `api.save_draft(form, definition, modified)`, `api.publish(form, change_note=None)`, `api.get_version(version)`, `api.compare_versions(a, b)`, `api.restore_as_draft(version)`, `api.archive(form)`.
  - Every builder call starts with `require_designer()`.
  - `save_draft` refuses with "Changed by <full name>, reload" when `modified` is older than the stored `modified`.

- [ ] **Step 1: Write failing tests:**
  - `test_first_publish_is_v1`.
  - `test_second_publish_is_v2_and_current`.
  - `test_unchanged_publish_refused`.
  - `test_version_cannot_be_edited`.
  - `test_version_not_deletable`.
  - `test_duplicate_version_no_refused` (insert a second row with the same `form`/`version_no` directly and expect `frappe.UniqueValidationError` or `frappe.DuplicateEntryError`).
  - `test_publish_requires_designer` (a user without the role gets `PermissionError`).
  - `test_save_draft_conflict`.
  - `test_compare_reports_added_removed_changed`.
  - `test_restore_as_draft_copies_definition`.
  - `test_invalid_draft_not_published` (no version is created).
- [ ] **Step 2:** Run the tests. Expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests. Expect PASS.
- [ ] **Step 5:** Commit `feat: locked form versions and publish`.

---

### Task 6: Context-provider interface

**Files:**
- Create: `forms_core/context.py`.
- Modify: `hooks.py` to read `forms_core_context_providers` (dict of doctype → dotted class path).
- Test: `forms_core/tests/test_context.py` (with a test provider class in `tests/utils.py`, registered by patching `frappe.get_hooks`).

**Interfaces:**
- Produces: `context.ContextProvider`, a base class (spec §7.1) with:
  - `values(self, context_name: str, context_row: str | None) -> dict[str, Any]`
  - `value_catalog(self) -> list[dict]`: `{"value": str, "label": str, "type": <field type name>}`; the builder lists these
  - `can_start(self, context_name, context_row, form: str) -> str | None`: a reason why not, or None
  - `has_permission(self, submission, user: str, ptype: str) -> bool`
  - `query_conditions(self, user: str) -> str`: SQL on `tabForm Submission`, limited to this context doctype
  - `outcomes(self) -> list[dict]`: `{"effect": str, "label": str}`
  - `on_submit(self, submission) -> None`, `on_cancel(self, submission) -> None`
- Produces: `context.get_provider(doctype: str | None) -> ContextProvider | None`, where `None` means no context.
- Produces: `definition.validate_against_provider(definition, provider) -> None`. It checks that every `fill_from.value` is in `value_catalog` and every outcome `effect` is in `outcomes`. Call it from `versions.publish` when the Form's `context_doctype` has a provider.
  - **Decision in this plan:** a Form gets a `context_doctype` Data field, optional, set in the builder. Add it to the Form DocType in this task.

- [ ] **Step 1: Write failing tests:**
  - `test_unknown_doctype_has_no_provider`.
  - `test_registered_provider_loaded`.
  - `test_publish_refuses_unknown_fill_from`.
  - `test_publish_refuses_unknown_outcome`.
  - `test_form_without_context_skips_provider_checks`.
- [ ] **Step 2:** Run the tests. Expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests. Expect PASS.
- [ ] **Step 5:** Commit `feat: context provider interface`.

---

### Task 7: Form Submission: start, save, submit, cancel, amend

**Files:**
- Create: the `Form Submission` DocType (spec §3.1: submittable; `account`, `form` Link reqd, `form_version` Link reqd, `answers` JSON, `context_doctype` Link DocType, `context_name` Dynamic Link, `context_row` Data, `started_by` Link User, `submitted_by` Link User, `submitted_on` Datetime, `amended_from`; `track_changes = 1`; autoname `hash`; indexes per spec §3.1 in `on_doctype_update`).
- Create: `forms_core/submissions.py`.
- Modify: `forms_core/permissions.py` (submission `has_permission` and `get_permission_query_conditions` hooks), `hooks.py`, `api.py`.
- Test: `forms_core/tests/test_submissions.py`.

**Interfaces:**
- Consumes: `get_type`, `field_index`, `ordered_fields`, `evaluate`, `get_provider`, `looks_like_secret`.
- Produces:
  - `submissions.start(form: str, context_doctype=None, context_name=None, context_row=None) -> str`.
    - It uses `current_version`, and refuses with a message if there is none or the form is Archived.
    - `provider.can_start` must return None.
    - It writes `fill_from` values from `provider.values(...)` into answers.
  - `submissions.save_answers(name: str, changes: dict) -> dict`, which returns the normalised answers. It merges by field ID, then:
    1. Refuses an unknown ID (Review Focus 1).
    2. Normalises each changed value through its type (a `ValueError` becomes a field error).
    3. Refuses changes to a locked `fill_from` field.
    4. Re-applies locked `fill_from` values from the provider.
    5. Removes answers for fields whose `show` (or section `show`) is false (Review Focus 2).
    6. Runs the secrets check on `text_values` of every changed answer, including table cells (Review Focus 4).
    7. Checks that every file URL in the answers is a `File` attached to this submission.
    8. Enforces the 1,000,000-byte limit.
    9. Saves. Drafts save with gaps.
  - `submissions.check_complete(doc) -> list[dict]`, run from `before_submit`, for visible fields only:
    - required, or `required_when` true, and the answer is empty
    - the type's `validate`
    - `checkbox.must_tick`
    - The secrets check on all answers.
    - Errors are raised together as `FormValidationError`.
  - **On submit:** sets `submitted_by` and `submitted_on`, and calls `provider.on_submit`. **On cancel:** calls `provider.on_cancel`.
  - **Permissions:**
    - With a provider, `has_permission` and `query_conditions` delegate to it.
    - Without a provider, the owner or a designer may access the submission.
    - Files attached to a submission follow it through Frappe's attached-document check.
- **API:** `api.start_submission(form, context_doctype=None, context_name=None, context_row=None)`, `api.get_submission(name)` (returns the answers plus the version definition), `api.save_answers(name, changes)`, `api.submit(name)`, `api.cancel(name)`.
  - Each call checks document permission.

- [ ] **Step 1: Write failing tests,** using the Task 6 test provider:
  - Starting and saving:
    - `test_start_uses_current_version`
    - `test_start_refused_when_provider_says_no`
    - `test_fill_from_written_on_start`
    - `test_locked_fill_from_cannot_be_changed`
    - `test_draft_saves_with_gaps`
  - Refused input:
    - `test_unknown_field_refused`
    - `test_wrong_shape_refused`
    - `test_hidden_answer_removed_on_save`
    - `test_secret_in_table_cell_refused`
    - `test_unicode_text_kept` (a 5,000-char mixed-script string round-trips)
    - `test_file_not_attached_refused`
    - `test_answers_over_limit_refused`
  - Submit and cancel:
    - `test_submit_reports_all_missing_required`
    - `test_required_when_enforced_on_submit`
    - `test_hidden_required_field_not_required`
    - `test_submit_sets_submitted_by`
    - `test_provider_on_submit_called`
    - `test_cancel_calls_provider`
    - `test_amend_links_original`
  - Access:
    - `test_user_without_provider_permission_cannot_read`
    - `test_query_conditions_hide_other_contexts`
- [ ] **Step 2:** Run the tests. Expect FAIL.
- [ ] **Step 3:** Implement. Return `drafts_on_older` counts in `versions.py` now that submissions exist.
- [ ] **Step 4:** Run the tests. Expect PASS.
- [ ] **Step 5:** Commit `feat: form submissions with server-side checks`.

---

### Task 8: Moving drafts to a newer version

**Files:**
- Modify: `forms_core/submissions.py`, `forms_core/api.py`.
- Test: `forms_core/tests/test_submissions.py` (class `TestUpgradeDraft`).

**Interfaces:**
- Produces:
  - `submissions.upgrade_draft(name: str) -> dict`, returning `{"from": version, "to": version, "dropped": [field ids]}`. It moves a draft to its form's `current_version`:
    1. Keep answers whose ID exists in the new version with the same type and still normalises.
    2. Drop the rest.
    3. Re-apply `fill_from` and the hidden-field removal.
    4. Save, with a comment on the document listing what was dropped. `track_changes` records the rest.
  - A submitted, cancelled or already-current draft gives a `FormValidationError`.
- Produces: `submissions.upgrade_all_drafts(form: str) -> int` (designer only).
- **API:** `api.upgrade_draft(name)` (submission write permission) and `api.upgrade_all_drafts(form)` (designer).

- [ ] **Step 1: Write failing tests:**
  - `test_draft_stays_on_old_version_after_publish`
  - `test_upgrade_keeps_answers_by_id`
  - `test_upgrade_drops_removed_field`
  - `test_upgrade_drops_type_changed_answer`
  - `test_submitted_cannot_upgrade`
  - `test_upgrade_all_counts`
  - `test_upgrade_all_requires_designer`
- [ ] **Step 2:** Run the tests. Expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests. Expect PASS.
- [ ] **Step 5:** Commit `feat: move drafts to the current version`.

---

### Task 9: Export and import

**Files:**
- Create: `forms_core/transfer.py`.
- Modify: `forms_core/api.py`.
- Test: `forms_core/tests/test_transfer.py`.

**Interfaces:**
- Produces:
  - `transfer.export_form(form: str, version: str | None = None) -> dict`: `{"format": "forms_core/1", "form": {title, key, subtitle, icon, color, context_doctype}, "definition": {...}}`, from the given version, or from the draft if `version` is None.
  - `transfer.import_form(data: dict, key: str | None = None) -> str`: creates a Draft Form.
    - **Every section, field and table-column ID is replaced with a fresh `new_id`.** Rule references are rewritten to the new IDs.
    - The definition goes through `validate_definition` before saving.
    - If the form key is already taken, it raises a field-linked error unless `key` is given.
  - Plan 7 uses `import_form` to load the five template files on migrate.
- **API:** `api.export_form(form, version=None)` and `api.import_form(data, key=None)`, both designer only.

- [ ] **Step 1: Write failing tests:**
  - `test_export_then_import_round_trip` (same labels and types; all IDs different).
  - `test_import_rewrites_rule_references` (the imported rule still evaluates the same on renamed answers).
  - `test_import_existing_key_refused`.
  - `test_import_invalid_definition_refused`.
  - `test_import_requires_designer`.
- [ ] **Step 2:** Run the tests. Expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests. Expect PASS.
- [ ] **Step 5:** Commit `feat: form export and import`.

---

### Task 10: CI and documentation for `forms_core`

**Files:**
- Create: `.github/workflows/ci.yml` in `forms_core`, a copy of DeployOps' server job with `--app forms_core`, plus a `js` job running `yarn install --frozen-lockfile && yarn test`.
- Create: `README.md`, a short guide to the data model, the hooks (`forms_core_field_types`, `forms_core_context_providers`, `forms_core_designer_roles`) and the API list from spec §9.
- Create: `.github/workflows/linter.yml`, a copy of DeployOps'.

- [ ] **Step 1:** Run `ruff check forms_core && ruff format --check forms_core`. Expect no findings.
- [ ] **Step 2:** Run the full suite: `bench --site deployops.local run-tests --app forms_core`, then `cd js && yarn test`. Expect all pass.
- [ ] **Step 3:** Commit `chore: CI and README`.
