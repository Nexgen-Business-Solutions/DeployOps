# DeployOps v2: form builder and form engine (design)

**Status:** APPROVED by the product owner on 2026-11-05. Items marked **[default]** were proposals; the owner accepted all of them (see §12).

**Supersedes for v2:** the "one native DocType per checklist" decision in `docs/CHECKLIST_ARCHITECTURE.md` §1. v1 keeps that design. In v2, the owner chose user-designed forms on purpose (2026-11-05). That is the dynamic-form approach AGENTS.md warns against unless it is justified, and §1 below gives the justification.

---

## 1. Goal and scope

**Who it's for.** First the company's own staff, who manage installation jobs. Later, the general public, with Jotform-style sign-up. v2.0 is built for the company, and the design has to grow into the public product without a rewrite.

**What v2.0 delivers**
- A visual **form builder** in the React app, where Administrators and Managers design, preview and publish forms.
- A **form engine** that stores locked form versions and submissions, checks answers on the server, and builds report tables.
- **Connection to jobs and machines**:
  - Rules decide which forms each machine needs.
  - Supervisors can override them per job.
  - One machine can need several forms.
  - Required forms block the machine until submitted.
- **The five v1 checklists rebuilt in the builder** as the acceptance test. If the builder can't reproduce them, it isn't done.

**Not in v2.0 (later phases, §11).** Public sign-up, accounts with members, plans and billing, analytics database, webhooks, editing a form together live, offline filling, calculated fields.

**v1 and v2.** v1 (tag `v1.0`) keeps its five hard-coded DocTypes. v2 has none of them; every form comes from the builder. No v1 data is migrated.

### Why a form engine and not a DocType per form
Both were considered, including generating a real DocType on each publish (one per form, or one per version).

**What a DocType per form does well:** typed columns, Desk reports, and Frappe's built-in required/show-when.

**Why it doesn't scale:**
- **Every publish changes the database on a live site.** MariaDB commits table changes immediately, so a failed publish can't be rolled back, and changing large tables locks them.
- **Locked versions (§3.3) need one table per version.** Tables then multiply by forms × versions × accounts, and every report has to combine them.
- **MariaDB caps a row at 65 KB.** Frappe's `varchar(140)` fields limit a form to roughly a hundred short text fields.
- **A bad publish damages stored answers.** With an engine, it only produces a bad definition, which can be fixed.

**What large systems do.** Metadata-driven platforms such as Salesforce never change the database when a customer changes their data model. Form products (Jotform, KoboToolbox/ODK) store locked definitions, store submissions as documents, and build report copies from them.

**Chosen design.** Forms and answers are stored as data. Typed report tables are built from them in the background, which gives the real columns a DocType per form would have given, without its risks (§4).

---

## 2. Components

| Part | Purpose | Lives in |
|---|---|---|
| Data model | Accounts, forms, locked versions, submissions | `forms_core` |
| Field-type plug-ins | One module per field type (builder, filling, checks, storage, report column, PDF) | `forms_core` (server + front end) |
| Rules language | Show-when, required-when and outcomes, written as data and read the same way in browser and server | `forms_core` |
| Report tables | Typed copies of submissions for Desk reports and exports | `forms_core` |
| Context providers | How the engine connects to the outside world without knowing about jobs | interface in `forms_core`; job provider in `deployops` |
| Builder UI | Design, preview, publish, versions | React app |
| Filling UI | The technician's form screen (v1's screen made generic) | React app |
| Job connection | Form rules, each machine's form list, blocking | `deployops` |

**`forms_core` is its own Frappe app** in its own repository **[default]**, and DeployOps depends on it, the same way TrixaPOS apps depend on `trixapos_core`. The engine never imports DeployOps code. That way it can later run on its own servers or sites for the public product.

---

## 3. Data model

Every engine record has an `account` from day one. v2.0 creates one account (the company) on install, and everything defaults to it.

### 3.1 DocTypes in `forms_core`

| DocType | What it is | Key fields |
|---|---|---|
| **Form Account** | Who owns forms. Only one in v2.0. | title, status |
| **Form** | A form as the builder sees it. Not versioned itself. | account; title; `key` (permanent slug, unique per account, e.g. `cashmatic-installation`); status (Draft / Published / Archived); `draft_definition` (JSON, the working copy); `current_version`; card appearance (icon, colour, subtitle) |
| **Form Version** | One publish. Can't be changed once created; the server refuses edits and deletes. | form; `version_no` (1, 2, 3…); `definition` (JSON); `schema` (format version of the JSON); `definition_hash`; published by/on; change note; references (file URL + fingerprint) |
| **Form Submission** | One filled-in form. Submittable (Draft → Submitted → Cancelled; can be amended). | account; form; `form_version`; `answers` (JSON); `context_doctype`, `context_name`, `context_row`; started by; submitted by/on |

**Indexes:**
- Submission (account, form, docstatus)
- Submission (context_doctype, context_name)
- Version (form, version_no) unique

### 3.2 Definition JSON
```json
{ "schema": 1,
  "sections": [
    { "id": "s_k2m9", "title": "Network", "description": "…", "show": { … },
      "fields": [
        { "id": "f_8k2m", "key": "wifi_ssid", "type": "text",
          "label": "Wi-Fi name", "help": "…", "required": true,
          "show": { … }, "required_when": { … },
          "fill_from": { "value": "serial_no", "locked": true },
          "outcomes": [ { "when": { … }, "effect": "block_machine" } ],
          "config": { … } } ] } ],
  "references": [ { "file": "/private/files/…pdf", "hash": "…", "title": "…", "show_in": ["s_k2m9"] } ] }
```
- **`id`:** generated when a field (or section) is created, unique within the form, and **never changed or reused** in any later version. Answers, report columns and version upgrades all use it.
- **`key`:** readable name for the API and exports, unique within a version. It can be renamed.
- **`type` and `config`:** `type` picks the plug-in (§5.1). Only that plug-in reads `config`.
- **`schema`:** the version of this JSON format. The server keeps a reader for every format version it has ever stored.

### 3.3 Versions
- **Publishing:**
  1. The server checks `draft_definition` (§6.3).
  2. It writes Form Version *n+1* and sets `current_version`.
  3. It starts the report-table update (§4).
  
  A publish with nothing changed (same hash) is refused.
- **Which version a submission uses:** a new submission uses `current_version`. A draft stays on the version it started on, and can be finished there.
- **Moving drafts up:** an admin can move drafts to the current version, for one form or one draft at a time.
  - Answers carry over by field `id`.
  - Answers to removed fields are dropped.
  - Answers that don't pass the new field type's checks are dropped.
  - The submission's change history (`track_changes`) records the move and what was dropped.
- **No snapshot needed.** A submission points at a version that can't change, so the version is the record of the questions. This replaces v1's `submission_snapshot`.

### 3.4 Answers JSON
```json
{ "f_8k2m": "Shop-Guest",
  "f_p4x1": [ { "_row": "r_1", "f_c9": "Monday", "f_c10": "08:00" } ],
  "f_sg7":  { "file": "/private/files/…png", "signer": "J. Doe",
              "signed_at": "…", "captured_by": "tech@…" } }
```
- **Keys:** answers are keyed by field `id`, and each value is shaped by its field type.
- **Tables:** repeating tables are lists of rows, each with a row `_row` ID.
- **Files:** photos, files and signatures are **private Frappe File records attached to the submission**. The answers hold only a reference.
- **Limits:** the answers JSON is capped at 1 MB; files don't count toward it.
- **Hidden fields:** answers to fields hidden by their show-when are removed on save, so stored answers always match what was visible.

### 3.5 Permissions (engine level)
- **Designing:** create, edit, publish, archive and import forms is **Administrator and Manager** only, enforced in the whitelisted API and in DocType permissions.
- **Submissions:** who can read and write them is decided by the context provider (§7.1). With no context, only the creator and Administrators can access them (public phase: account members).
- **Files:** follow their submission's access.

---

## 4. Report tables

Report tables give real columns for Desk reports, filters and exports. **They are always built from submissions, can always be rebuilt, and are never the source of truth.**

- **One per form:** each form gets one generated read-only DocType covering all its versions.
  - Its name is made from the form `key` on first publish (e.g. **Form Report Cashmatic Installation**) and is never renamed.
  - It's created and changed through Frappe's own DocType save, so Frappe handles the database changes on MariaDB or Postgres. There's no hand-written SQL.
- **Columns:**
  - **Built in:** `submission` (unique), `form_version`, status, context doctype/name/row, account, submitted by/on.
  - **One column per field `id`,** labelled with the field's latest label. The plug-in decides the column type (§5.1).
  - **Long or free text uses TEXT columns,** which MariaDB stores outside the row (about 20 bytes count toward the row limit). Short Data columns are used only where filtering needs them.
- **Changes are add-only:**

  | Change | What happens |
  |---|---|
  | Field added | New column |
  | Label renamed | Column label changes; no database change |
  | Field removed | Column stays with its data, labelled "(removed in vN)", hidden by default |
  | Field type changed | New column (`f_8k2m_2`); the old one keeps older versions' values |
  | Too many columns | Extra columns go to a **… Part 2** table with one row per submission. The split happens at a fixed column budget, well below MariaDB's 1,017-column limit. |

- **Repeating and fixed-row tables:** each gets a child report table (**… Rows: <field label>**), one row per answer row.
- **Keeping them up to date (background queue, one job at a time per form):**
  - **After a publish:** add the new columns.
  - **After a submit, cancel or amend:** write that submission's row, using `modified` so a newer update always wins.
  - **If an update fails:** answers still save, the form is flagged "report out of date", and the error is logged. **Rebuild report** recreates the table from all submissions.
  - **Nightly check:** compares counts and dates with the submissions and fixes any gaps.
- **Drafts are not included [default].** Reports are about finished work, and autosave would rewrite rows constantly. Drafts are visible on the job screens.
- **Who can see them:** Desk read access is **Administrator and Manager only [default]**. Generated DocTypes can't have their own server-side permission code, so no narrower access is granted in Desk. Supervisors get reports filtered to their jobs through an app screen that applies job visibility on the server.

---

## 5. Field types and rules language

### 5.1 Field-type plug-ins
Each type is one plug-in with a server part and a front-end part. Both use the same type name.

| Part | Server (Python) | Front end (React) |
|---|---|---|
| Settings | `validate_config(config)` | default settings, *Settings panel* |
| Answer | `normalize(value)`, `validate(value, field, ctx) → errors`, `is_empty(value)` | how it's filled in, how it looks once answered |
| Output | `report_columns(field)`, `to_text(value)` (PDF/export) | the builder palette entry (icon, label) |

**Registering types:**
- Server types are registered through a hook (`forms_core_field_types`), so other apps can add their own.
- Front-end types are registered in one list.
- The builder palette and the server check both come from these registrations. The core never has code for a specific type.

**Field types in v2.0.** Taken from what the five v1 forms use, which across them is about 184 tick boxes, ~57 short texts, ~31 long texts, ~28 choices, 21 tables, 9 signatures, plus dates, times, numbers and currency.

| Type | Settings | Report column |
|---|---|---|
| `text` (one line) | max length | Data |
| `long_text` | — | Text |
| `number` | whole/decimal, min, max | Int / Float |
| `currency` | currency | Currency |
| `choice` | options, drop-down or buttons, "Other" with its own text | Data (+ Text for Other) |
| `multi_check` | options, minimum ticked, "Other" with its own text (v1's `ANY_OF` + `OTHER_ANSWERS`) | Text (ticked options joined) |
| `checkbox` | "must be ticked" (an acknowledgement) | Check |
| `yes_no` | — | Data |
| `date`, `time`, `datetime` | — | Date / Time / Datetime |
| `photos` | min/max count, caption on/off (v1's `MIN_ROWS`) | Int (count) |
| `files` | min/max count, allowed file types | Int (count) |
| `signature` | where the signer's name comes from: another field, or the job's technician (v1's `SIGNERS`) | Data (signer) + Datetime |
| `table` | columns (each a simple type above), min rows, **fixed rows** with labels that can't change (v1's `FIXED_ROWS`, e.g. opening hours, maintenance tasks) | child report table |
| `info` | text / formatted note shown to the technician | none |

v1's **Link** fields (customer, Item, Serial No…) become **fill from** job values (§7.2), not a field type.

### 5.2 Rules language
Used by `show`, `required_when` and outcome `when`. It's a small JSON format, and nothing in it is ever executed as code.

```json
{ "all": [ { "field": "f_8k2m", "op": "eq", "value": "Yes" },
           { "any": [ { "field": "f_q1", "op": "in", "value": ["A", "B"] },
                      { "field": "f_n2", "op": "gte", "value": 10 } ] } ] }
```
- **Operators:** `eq`, `ne`, `in`, `not_in`, `gt`, `gte`, `lt`, `lte`, `empty`, `not_empty`, `contains` (for multi-tick).
- **Groups:** `all`, `any`, `not`. Nesting is limited to depth 4.
- **References:** a rule can only refer to fields **earlier in the form**. Publishing refuses loops and references to fields that don't exist.
- **Two small readers,** one in Python and one in TypeScript, read the same format. One shared file of test cases (`rules_cases.json`) runs in both test suites, so the browser and server can't disagree.
- **The server decides.** The browser evaluates rules only so the technician sees them as they type.
- **Reserved for later:** calculated values (`"calc"`) are left out in v2.0, but the format leaves room for them.

### 5.3 Checks on every save and submit
- **Drafts** save even with missing answers, so autosave works.
- **Submit** checks:
  - required fields, required-when, minimum ticked, minimum/maximum, photo and row counts, fixed rows complete
  - each type's own `validate`
  - the **secrets check** on every text value and table cell, carried over from v1
- **Errors** point to field `id` (and row), so the app shows them on the right field.

---

## 6. Builder (React app)

### 6.1 Screens
1. **Forms list:** status, current version, how many rules use the form, last published. Actions: New, Duplicate, Archive, Import, Export.
2. **Builder:** three panels.
   - **Left, field types:** the plug-in palette. Drag a type onto the form, or click to add it after the selected field.
   - **Middle, the form:** sections (each is a step for the technician) containing fields. Drag to reorder or move between sections; duplicate (with new IDs) or delete.
   - **Right, settings for the selected field:** label, help text, `key`, required, **Show when**, **Required when**, the type's settings, **Fill from** (locked/editable), **Outcomes**.
3. **Top bar:** title, "Draft saved", Undo/Redo, Preview, Publish, Versions.
4. **Tabs on a form:** Documents, Card appearance, **Used by** (the Form Rules that use it).

Built for laptop and tablet screens, 1024px and wider. On phones, admins can view forms but not edit them.

### 6.2 Editing
- **Conditions editor:** a visual editor, "[field] [is / is not / is one of / > / <] [value]", with All of / Any of groups. Only earlier fields can be picked.
- **Preview:** the real technician screen at phone / tablet / desktop widths. *Fill sample job* fills in job values. Nothing is saved.
- **Autosave:** `draft_definition` is saved automatically. If two admins edit the same form, the second save is refused ("changed by X, reload").
- **Undo/Redo:** one place applies every edit, which gives undo and redo.
- **Drag and drop:** `@dnd-kit`, which works with the keyboard and screen readers.

### 6.3 Publish
1. **Server check.** Each error is linked to a field and shown on the form:
   - keys are unique, and IDs are never reused from any earlier version
   - rules refer to fields that exist, and there are no loops
   - each type's settings are valid
   - outcomes and fill-from values are ones the context provider offers
   - the form fits the report-table column budget
2. **Change summary** against the current version (fields added, removed, changed), with warnings such as "12 drafts are on v3 and will stay there unless moved up".
3. **Change note → Publish.**

### 6.4 Versions, documents, templates
- **Versions:** view any version read-only, compare two, or *Restore as draft*.
- **Reference documents:** attached to the form. Each can also show inside a chosen section or field; all appear in the Documents panel. A version records each file's URL and fingerprint, so replacing a document later doesn't change older submissions.
- **Export / Import** a form as JSON. Import gives every field a new ID and is checked like a publish. This is how forms move from test.site to production. The five rebuilt v1 forms become templates.

---

## 7. Connecting forms to jobs and machines

### 7.1 Context provider interface (`forms_core`)
An app registers a provider for a context DocType through the `forms_core_context_providers` hook. DeployOps registers one for `DeployOps Job`.

| Method | Job provider behaviour |
|---|---|
| `values(context)` → the values fields can be filled from | customer, address, contact, Item, Serial No, technician, planned date, company |
| `can_start(context, form)` | job in a working state, machine not cancelled, form planned for the machine |
| `has_permission(submission, user, ptype)` and `query_conditions(user)` | visible exactly when the job is: v1 job visibility, for records, files, reports and the API |
| `outcomes()` → the actions forms can trigger | `block_machine`, `flag_for_review` |
| `on_submit`, `on_cancel` | update the machine's form status; re-check blocking |

### 7.2 Which forms a machine gets (`deployops`)
- **Form Rule:** job type + equipment category → form, required/optional, order, active.
  - If a machine's Item is in several categories, it gets all their forms, each listed once.
  - Where one rule says required and another optional, required wins.
- **Job Device Form** (child of the job): one row per form planned for a machine. Each row records the form, required, where it came from (rule or override) and its submission.
  - Rows are created from the rules when a machine is added.
  - They update from the rules **until the first form on that machine is started**, then stay fixed **[default]**.
- **Supervisor override:** a Supervisor can add a form or remove an optional one. Removing a required form needs a **Manager and a reason [default]**. Every change goes in the job's Status Log.
- **Versions:** rows name the form; the version is fixed when that submission is started.

### 7.3 Filling forms on a job
- **The machine screen** lists that machine's forms, with Required/Optional and Not started / Draft / Submitted.
  - *Start* creates a submission with context job + machine row.
  - Each row has one live submission. A cancelled one can be started again; an amended one links to the original.
- **Fill from (locked or editable):**
  - While the form is a draft, locked values follow the job (the serial follows the machine row, as in v1's #22).
  - **On submit, the values are saved into the answers**, so the submission keeps its own copy.
- **Blocking:**
  - A machine can't be marked installed until all its required forms are submitted and no outcome has blocked it.
  - A job can't be completed until every machine that isn't cancelled passes.
  - v1's hard-coded "safety FAIL / handover No" becomes form outcomes.
  - `job_workflow` checks read the machine's form list instead of the v1 DocTypes.
- **Machine changes mid-job:**
  - **Machine cancelled:** its unsubmitted forms can't be submitted, and a Manager discards them.
  - **Serial swapped:** drafts follow the new serial; submitted forms keep theirs.
- **Home screen:** each form with an active rule is a card. Open jobs and needs-attention counts come from machine form lists. The sidebar and Overview keep working on the same data.

---

## 8. Technician side
- **Same screen as v1, now generic.** v1's form screen (sections as steps, progress, autosave, Documents panel, signatures, photo capture) is drawn from the version JSON through the front-end plug-ins. No form-specific code is left.
- **Save:** partial save as in v1: only changed answers are sent, the server merges them by field `id`, re-checks them and returns the normalised answers.
- **Connection:** online only in v2.0 **[default]**. The answers format and save endpoint are designed so offline filling with sync can be added later without changing the data model.
- **PDF reports:** internal and customer copies built from any version + answers **[default: included in v2.0]**, reusing v1's report code, which already works from a form's description rather than one fixed form. Each field can be marked internal-only so it is left out of the customer copy.

---

## 9. API (whitelisted, `forms_core.api`)

| Area | Calls |
|---|---|
| Builder | `list_forms`, `get_form`, `save_draft`, `publish`, `get_version`, `compare_versions`, `restore_as_draft`, `export_form`, `import_form`, `archive` |
| Filling | `start_submission(form, context)`, `get_submission`, `save_answers`, `submit`, `cancel`, `upgrade_draft` |
| Reports | `rebuild_report(form)`, `report_status(form)` |

DeployOps adds: `machine_forms(job, row)`, `override_machine_forms(...)`, and a home/card endpoint built from the Form Rules.

---

## 10. Testing

- **Rules:** shared `rules_cases.json` run by both Python and vitest.
- **Field types:** each plug-in tested for config checks, normalising, checking, empty values, report column and text output.
- **Versions:**
  - a published version can't be edited
  - IDs are never reused
  - drafts stay on their version
  - upgrade carries answers by `id` and drops removed ones
  - a publish with no changes is refused
- **Report tables:**
  - add-only changes
  - type change makes a new column
  - Part 2 split
  - out-of-order updates
  - rebuild matches the submissions
  - a failed update doesn't stop saving
- **Permissions:**
  - only Admins and Managers can design and publish
  - submissions, files and report access follow job visibility
  - negative tests for technicians outside the job and direct API calls
- **Jobs:**
  - rules produce the machine's form list
  - several forms per machine
  - override rules, with the Manager-only removal of required forms
  - blocking
  - machine cancelled
  - serial swap
- **Acceptance:** the five v1 forms rebuilt in the builder, then each filled and submitted start to finish on a test job, including the BellaBot safety-FAIL block.
- Tests run on deployops.local, as for v1.

---

## 11. Phases and rollout

| Phase | Contents |
|---|---|
| **v2.0** (company) | `forms_core` app; data model with account; plug-ins (§5.1); rules language; builder; job connection; generic technician screen; report tables (one per form, Part 2 split, rebuild); basic PDFs **[default]**; five v1 forms rebuilt as templates |
| **v2.x** | Webhooks and integrations; calculated fields; supervisor report screen improvements; offline filling |
| **v3** (public) | Sign-up, account members and roles, plans and limits, template gallery; free accounts share a site, large customers get their own site on Frappe Cloud; data split by account/date; analytics database fed from submission events; editing a form together live |

**Branches [default]:**
- `release/v1` is created from tag `v1.0` for the remaining v1 work (#15, #30, #32).
- v2 work goes on `main` via task → feature → main.
- The v1 checklist DocTypes are removed from `main` only once the five v2 forms pass acceptance.

---

## 12. Owner decisions (defaults accepted 2026-11-05)

| # | Decision | Accepted |
|---|---|---|
| 1 | Offline filling in v2.0? | Online only; offline can be added later |
| 2 | PDF reports in v2.0? | Yes, basic internal + customer copies |
| 3 | App name and repository | `forms_core`, its own repository |
| 4 | Branches | `release/v1` from `v1.0`; v2 on `main` |
| 5 | GitHub issues | Claude drafts the v2 epic/features/tasks for the owner to create |
| 6 | When a machine's form list stops following the rules | When its first form is started |
| 7 | Removing a required form from a machine | Manager, with a reason |
| 8 | Drafts in report tables | Not included |
| 9 | Desk access to report tables | Administrator and Manager only |

## 13. Risks
- **Builder size:** the builder is the largest piece. If it slips, the engine and job connection can be shipped first, with forms imported from JSON.
- **Rebuilding the five v1 forms** may turn up rules the plug-ins don't cover. That's the purpose of the acceptance test; new types or settings get added, not special cases.
- **Report tables** depend on background jobs; the nightly check and Rebuild cover missed updates.
- **Checks split across browser and server** could drift apart; the shared test cases and "server decides" contain that.
