# v2 Plan 4: Technician screen (implementation plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Technicians fill v2 forms in the React app. The screen is v1's form screen made generic and drawn from the version JSON through front-end field-type plug-ins. The job screen lists each machine's forms, and the home grid shows a card for each form with an active rule, next to the v1 cards. At the end the user can try it all on test.site (localhost:8004).

**Architecture:**
- **Renderer.** A pure `FormRenderer` takes a version definition, answers and a render context, and draws the sections as steps through a single list of field plug-ins (`src/forms/fields`). It has three modes: `fill`, `readonly` and `preview`. Plan 5's builder Preview reuses it as it is.
- **Form screen.** A page (`/s/:name`) loads `forms_core.api.get_submission`. An `AnswerQueue` autosaves only the changed answers through `forms_core.api.save_answers`, and the page merges back the normalised answers the server returns.
- **Job connection.** Machines that use forms show a `MachineForms` list on the job screen, built on Plan 3's `machine_forms` APIs. Cards come from `form_cards` merged with the v1 cards.
- **Server.** Two small additions are needed: forms_core's `get_submission` returns what the screen needs, plus a guarded reference-file download, and `machine_forms` returns the discard and cancel flags.

**Tech Stack:** React 19 + TypeScript 6 + Vite 8 + Tailwind 4 (doppio app in `deployops/frontend`), vitest 5 (node environment, `react-dom/server` for render tests), lucide-react; Frappe v16 / Python 3.14 for the server additions.

**Spec:** `docs/superpowers/specs/2026-11-05-v2-form-builder-design.md`:
- §8 (technician side)
- §7.3 (the machine screen, Start, fill from, the home screen)
- §5.1 (the front-end half of the field-type plug-ins)
- §5.2 ("The browser evaluates rules only so the technician sees them as they type")
- §3.4 (answer shapes)

This plan builds on Plan 1 (`2026-11-05-v2-plan-1-forms-core-engine.md`), Plan 2 (`2026-11-08-v2-plan-2-report-tables.md`) and Plan 3 (`2026-11-08-v2-plan-3-job-connection.md`; its Task 5 and Task 6 fix the API shapes used here).

**Not in this plan:**
- The builder, its Settings panels and its Preview screen (Plan 5). This plan makes the renderer and plug-ins ready for them.
- PDF reports and their download buttons (Plan 6).
- The Supervisor report screen on `report_rows` (see the open question in the hand-off).
- Moving a draft to a newer version (`upgrade_draft`). That is an admin action and belongs with the builder.
- Offline filling. The app is online only (§12 decision 1).

## Global Constraints

- **Repositories and branches:**
  - **deployops** (`/home/kimbi/frappe/massarie_project/apps/deployops`): branch `task/v2-technician-screen`, created from `task/v2-job-connection` once Plan 3 Task 6 is committed. Do not start before that commit exists, because `api/forms.py` and the docs are being changed for Task 6.
  - **forms_core** (`/home/kimbi/frappe/massarie_project/apps/forms_core`): Task 1 only, on the existing branch `task/v2-forms-core-reports`.
- **Commits:**
  - Local only, with short one-line messages.
  - `git add` explicit paths only. Never add the `.claude/worktrees/...` gitlink.
  - No push and no GitHub activity.
- **Front end:**
  - Tabs, as in `pages/Form.tsx`.
  - No new npm dependencies. Render tests use `renderToStaticMarkup` from `react-dom/server`, in vitest's default node environment.
  - Checks: `cd frontend && yarn typecheck && yarn lint && yarn test`, all green at the end of every front-end task.
- **No form-specific code:** nothing in `src/forms/`, `pages/Submission.tsx` or `components/MachineForms.tsx` names a form, field key or job type. The page reads only these context value keys of the job provider, for its header: `customer_name`, `item_name`, `item_code`, `serial_no` and `technician`.
- **Rules evaluator:** **copy** `forms_core/js/src/rules.ts` verbatim to `frontend/src/forms/rules.ts`, under a two-line header naming its source.
  - It is a copy and not an import path because the CI front-end job checks out deployops alone and must type-check, test and build without a sibling `forms_core`.
  - Drift is caught by Task 2's `rules.parity.test.ts`. When `../../forms_core` exists, that test asserts the copy matches the source byte for byte below the header and runs `forms_core/rules_cases.json`. When it doesn't exist, the test is skipped.
- **Answer shapes sent to the server.** These are exactly what forms_core's normalisers accept. Any other shape fails the whole save.

  | type | value |
  |---|---|
  | `text`, `long_text` | string; `""` is sent as `null` |
  | `number` | number; whole numbers when `config.decimal === false` |
  | `currency` | number |
  | `checkbox` | `true` / `false` (never 1/0) |
  | `yes_no` | `"Yes"` / `"No"` |
  | `date` | `"YYYY-MM-DD"` |
  | `time` | `"HH:MM:SS"` |
  | `datetime` | `"YYYY-MM-DD HH:MM:SS"` |
  | `choice` | an option string, or `{"other": text}` |
  | `multi_check` | `{"selected": [..], "other": text \| null}` |
  | `photos`, `files` | `[{"file": "/private/files/…", "caption": text \| null}]` |
  | `signature` | send `{"file": url}`; the server stamps and returns `{file, signer, signed_at, captured_by}` |
  | `table` | `[{"_row": "r_xxxxxx", <column id>: value}]` |
  | `info` | never sent |

- **Field-type config keys read by the plug-ins** (from `forms_core/field_types/*`):
  - `text`: `max_length`
  - `number`: `decimal`, `min`, `max`
  - `checkbox`: `must_tick`
  - `choice`: `options`, `display` (`dropdown` | `buttons`), `allow_other`
  - `multi_check`: `options`, `min_selected`, `allow_other`
  - `photos`: `min`, `max`, `captions`
  - `files`: `min`, `max`, `extensions`
  - `signature`: `signer_from`
  - `table`: `columns` (each `{id, type, label, required, config}`, with type in `text, long_text, number, checkbox, yes_no, choice, date, time`), `min_rows`, `fixed_rows {column, labels}`
  - `info`: `text`
- **Client checks** reproduce `forms_core.submissions.check_complete` and each type's `validate`, using the server's messages word for word:
  - "This field is required"
  - "This box must be ticked"
  - "Select at least {n}"
  - "Add at least {n}" and "Add at most {n}"
  - "Must be at least {min}" and "Must be at most {max}"
  - "Add at least {n} rows"
  - "Rows must match the fixed row labels"
  - "File type .{ext} is not allowed"

  The server decides. Errors from the server (`form_errors`) always replace the client's.
- **Copy:**
  - Text inputs keep v1's placeholder "Never type passwords, PINs, OTPs or pairing codes."
  - A locked fill-from field shows the hint "From the job".
  - The submit button reads "Submit form", and its dialog "Submit form?" with the warning "The answers are locked once submitted."
- **Python** (Tasks 1, 7 and 9):
  - ruff `line-length = 110`, tabs. User-facing messages go through `_()`.
  - Tests run on deployops.local: `bench --site deployops.local run-tests --app <app> --module <module>`, from `/home/kimbi/frappe/massarie_project`.
- **Migrations:** after the server tasks, and in Task 9, run `bench --site deployops.local migrate && bench --site test.site migrate`.

## Review Focus

1. **Cascading hidden answers.** A technician answers B (shown when A = Yes) and C (shown when B is filled), then changes A to No. B and C are both hidden, and C doesn't count as missing, exactly as the server's progressive removal does. → Task 2 `visibleFieldIds hides a chain once its first link is hidden`.
2. **One bad answer in a batch.** A batch holds a secret-looking text, or a file the server rejects, along with other answers. The other answers still save, and the bad field shows the server's message and stays pending. → Task 3 `retries once without the fields the server rejected`.
3. **Leaving within the autosave delay.** The technician types, then taps Back or switches app before the 800 ms delay. The pending answers are still sent. → Task 3 `dispose sends what is pending`, plus the `pagehide` wiring in Task 6.
4. **Value shapes.** A checkbox sent as `1`, a time sent as `"08:30"`, or an empty text sent as `""` makes every save fail. → Task 4 `conversions produce the server's shapes`.
5. **Definitions the app can't fully draw:** a field type the app doesn't know (a later plug-in), or a fixed-row table that was never touched. The first shows a placeholder and doesn't crash the screen. The second gets its labelled rows, so submit doesn't fail with "Rows must match the fixed row labels". → Task 5 `unknown type renders a placeholder` and Task 2 `fixedRowSeeds fills untouched visible fixed tables`.

---

## File structure

```
forms_core/forms_core/api.py                  # get_submission keys, reference_file      (Task 1)
deployops/deployops/api/forms.py              # can_discard, can_cancel                   (Task 7)
deployops/deployops/tests/forms_demo.py       # seed(technician) for test.site            (Task 9)
frontend/src/forms/
  rules.ts                 # verbatim copy of forms_core/js/src/rules.ts
  types.ts                 # Definition, FieldDef, Answers, FormError, SubmissionView, MachineForms…
  logic.ts                 # visibility, required, checkComplete, errorsByField, progress, rows
  queue.ts                 # AnswerQueue (autosave of changed answers)
  fields/index.ts          # FieldPlugin, RenderContext, FIELD_TYPES, getPlugin
  fields/convert.ts        # input string <-> server value conversions
  fields/basic.tsx         # text long_text number currency checkbox yes_no date time datetime info
  fields/choice.tsx        # choice multi_check
  fields/table.tsx         # table
  fields/files.tsx         # photos files
  fields/signature.tsx     # signature
  references.ts            # screen references -> v1 DocumentsDock / ReferenceCard shapes
  machine.ts               # formButtons(entry)
  FormRenderer.tsx
frontend/src/pages/Submission.tsx    # /s/:name
frontend/src/pages/FormJobs.tsx      # /f/:form
frontend/src/components/MachineForms.tsx
modified: App.tsx, pages/Job.tsx, pages/Home.tsx, pages/Overview.tsx, pages/CardJobs.tsx,
          components/AppShell.tsx, components/form/DocumentsDock.tsx, lib/api.ts, lib/cards.ts,
          lib/pdf.ts, lib/types.ts, lib/image.ts
tests: forms/*.test.ts(x), forms/fields/fields.test.ts, lib/*.test.ts,
       deployops/tests/test_forms_screen.py, forms_core/tests/test_filling_api.py
```

---

### Task 1: forms_core: what the form screen needs (forms_core repo)

**Files:** Modify `forms_core/api.py`. Test: `forms_core/tests/test_filling_api.py` (new; reuse the helpers in `forms_core/tests/utils.py` and the test provider set-up from `test_submissions.py`).

**Interfaces:**
- Produces: `get_submission(name: str) -> dict` (GET). The existing keys stay, and these are added:
  - `title: str` (Form title) and `version_no: int`
  - `context_values: dict`: `provider.values(context_name, context_row)`, or `{}` without a provider or context
  - `can_write: bool`: docstatus 0 and `frappe.has_permission("Form Submission", "write", doc)`
  - `can_submit: bool`: docstatus 0 and the `submit` permission
  - `submitted_by: str | None` (the full name) and `submitted_on: str | None`
  - `references: [{"title": str, "url": str, "show_in": [str]}]`, from the version definition. `url` is the file itself for `/files/…`, and `/api/method/forms_core.api.reference_file?submission=<name>&file=<urlencoded file>` for `/private/files/…`.
- Produces: `reference_file(submission: str, file: str) -> None` (GET, `methods=["GET"]`).
  - `check_permission("read")` on the submission.
  - `file` must be the `file` of one of the references in that submission's version definition. Otherwise raise `frappe.PermissionError`.
  - Serves the File content: `frappe.local.response.filename`, `.filecontent`, `.type = "download"`, `.display_content_as = "inline"`.
  - Why it's needed: reference files are private Files attached to the Form, which technicians cannot read.

- [ ] **Step 1: Write the failing tests:**
  - `test_get_submission_screen_keys`: the new keys are present. `context_values` equals the provider's values, `version_no == 1`, and `title` is the form title.
  - `test_flags_follow_permission`: the owner of a draft gets `can_write` and `can_submit` True. After submit both are False. A reader without write gets `can_write` False.
  - `test_reference_urls`: a `/files/a.pdf` reference keeps its URL, and a `/private/files/b.pdf` one gets the `reference_file` URL with `file` urlencoded.
  - `test_reference_file_served_to_reader`: the response `filecontent` equals the File's content.
  - `test_reference_file_refuses_unlisted_file`: a private file that is not in the version's references raises PermissionError.
  - `test_reference_file_refuses_non_reader`.
- [ ] **Step 2:** Run `bench --site deployops.local run-tests --app forms_core --module forms_core.tests.test_filling_api`. Expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the module again, then the whole forms_core suite (`--app forms_core`). Expect PASS. Plan 3 Task 1 reported known designer-role failures; list any that remain, unchanged, in the report.
- [ ] **Step 5:** In the forms_core repo, commit `feat: submission screen data and reference download`.

---

### Task 2: Branch, types, rules copy and form logic

**Files:**
- Create: `frontend/src/forms/rules.ts` (copy), `forms/types.ts`, `forms/logic.ts`
- Modify: `lib/api.ts`
- Test: `forms/logic.test.ts`, `forms/rules.parity.test.ts`, `lib/api.test.ts`

- [ ] **Step 0:** In deployops, `git checkout -b task/v2-technician-screen task/v2-job-connection`, after confirming Plan 3 Task 6 is committed (`git log --oneline -1` shows `feat(v2): form cards and supervisor report`, or a later commit).

**Interfaces (Produces):**
- `forms/types.ts`:
  ```ts
  export type FieldDef = { id: string; key: string; type: string; label: string; help?: string;
    required?: boolean; show?: Rule | null; required_when?: Rule | null;
    fill_from?: { value: string; locked?: boolean }; outcomes?: { when: Rule; effect: string }[];
    config?: Record<string, unknown> };
  export type ColumnDef = { id: string; type: string; label: string; required?: boolean; config?: Record<string, unknown> };
  export type SectionDef = { id: string; title?: string; description?: string; show?: Rule | null; fields: FieldDef[] };
  export type Definition = { schema: number; sections: SectionDef[]; references?: { file: string; title: string; show_in: string[] }[] };
  export type Answers = Record<string, unknown>;
  export type TableRow = { _row: string } & Record<string, unknown>;
  export type FormError = { field: string | null; row: string | null; message: string };
  export type ScreenReference = { title: string; url: string; show_in: string[] };
  export type SubmissionView = { name: string; docstatus: 0 | 1 | 2; form: string; form_version: string;
    version_no: number; title: string; context_doctype: string | null; context_name: string | null;
    context_row: string | null; amended_from: string | null; answers: Answers; definition: Definition;
    context_values: Record<string, unknown>; can_write: boolean; can_submit: boolean;
    submitted_by: string | null; submitted_on: string | null; references: ScreenReference[] };
  ```
  Also `MachineFormEntry` and `MachineFormsView`, which copy Plan 3 Task 5's `machine_forms` shape exactly and add `can_discard: boolean` and `can_cancel: boolean` (Task 7). And `FormCard` and `FormJobRow`, which copy Plan 3 Task 6's `form_cards` and `form_jobs` shapes.
- `forms/logic.ts`:
  - `visibleFieldIds(def: Definition, answers: Answers): Set<string>` copies `submissions.visible_fields(remove=True)` on a copy of the answers:
    - walk sections and fields in order
    - a section's `show` and a field's `show` are evaluated against the answers left after earlier removals
    - a hidden field's answer is removed before later rules are evaluated
    - `info` fields are included when visible
  - `visibleSections(def, answers): SectionDef[]` returns the visible sections with only their visible fields, and drops sections left empty.
  - `isRequired(field: FieldDef, answers: Answers): boolean` is `required`, or `required_when` evaluating true.
  - `errorsByField(def, errors: FormError[], answers: Answers): { byField: Map<string, string>; general: string[] }`:
    - An error on a top-level field id is filed under that id.
    - An error on a table column id is filed under the table field's id as `"Row {n}: {column label}: {message}"`, where `n` is the 1-based position of `row` in that table's answer.
    - `field: null`, or an unknown id, goes to `general`.
    - Multiple errors on one field are joined with a space.
  - `topFieldOf(def, id: string): string` returns the table field's id for a column id, and `id` itself otherwise.
  - `newRowId(): string` is `"r_"` followed by 6 random lowercase base36 characters.
  - `fixedRowSeeds(def, answers): Answers` returns, for every visible `table` whose answer is empty and whose config has `fixed_rows`, the rows `labels.map(label => ({_row: newRowId(), [fixed_rows.column]: label}))`.
  - `displayValue(field, answers, values, mode: RenderMode): unknown` is `answers[field.id]`. In `preview` mode, a field with `fill_from` and no answer gets `values[fill_from.value]` instead.
- `lib/api.ts`: `ApiError` gains `formErrors: FormError[] | null`, read from the error body's `form_errors`. The constructor becomes `(message, status, formErrors = null)`.

- [ ] **Step 1: Write the failing tests** (`logic.test.ts` builds small definitions inline with `f_xxxx` ids):
  - `visibleFieldIds hides a chain once its first link is hidden` (Review Focus 1).
  - `a hidden section hides its fields and drops their answers for later rules`.
  - `required_when makes a field required`.
  - `errorsByField maps column errors to their table with the row number`, and `field null goes to general`.
  - `fixedRowSeeds fills untouched visible fixed tables` (Review Focus 5): labels in order, unique `_row` values matching `/^r_[a-z0-9]{6}$/`, and nothing for a hidden or already answered table.
  - `displayValue uses context values only in preview`.
  - `rules.parity.test.ts`:
    - `describe.skipIf(!existsSync(source))`, where `source` is `path.resolve(__dirname, "../../../../forms_core/js/src/rules.ts")`
    - `copy matches forms_core`: the copy without its header equals the source
    - `shared rule cases pass`: runs `forms_core/forms_core/rules_cases.json` through the copy's `evaluate`
  - `api.test.ts`: `keeps form_errors from a refused save`. A 417 body with `form_errors: [{field: "f_aaaa", row: null, message: "x"}]` gives `error.formErrors` with that list.
- [ ] **Step 2:** `cd frontend && yarn test`. Expect FAIL.
- [ ] **Step 3:** Copy `rules.ts` and implement.
- [ ] **Step 4:** `yarn typecheck && yarn lint && yarn test`. Expect PASS.
- [ ] **Step 5:** Commit `feat(v2): form logic for the technician screen`.

---

### Task 3: AnswerQueue (partial autosave)

**Files:** Create `frontend/src/forms/queue.ts`. Test: `forms/queue.test.ts` (vitest fake timers).

**Interfaces:**
- Consumes: `ApiError` with `formErrors` (Task 2).
- Produces:
  ```ts
  export type SaveState = "idle" | "saving" | "saved" | "offline" | "error";
  export class AnswerQueue {
    constructor(opts: {
      save: (changes: Answers) => Promise<Answers>;            // resolves to the server's normalised answers
      onSaved: (server: Answers, stillPending: Answers) => void;
      onState: (state: SaveState, error: ApiError | null) => void;
      fieldOf?: (errorField: string) => string;                 // column id -> table id; default identity
      delayMs?: number;                                         // default 800 (v1's AUTOSAVE_MS)
    });
    change(fieldId: string, value: unknown): void;               // newest value per field wins
    flush(): Promise<boolean>;                                   // true when nothing is left pending
    get pending(): Answers;
    dispose(): void;                                             // stop the timer; send what is pending, without waiting
  }
  export function mergeSaved(server: Answers, pending: Answers): Answers; // {...server, ...pending}
  ```
- Behaviour:
  - Only one `save` is in flight at a time. A `flush` called meanwhile waits for it and then sends what has queued since.
  - **Offline:** an `ApiError` with status 0 puts the batch back under any newer changes, with state `offline`.
  - **Refused fields:** an `ApiError` whose `formErrors` name fields of the batch (through `fieldOf`) sends one more save without those fields. The refused fields stay pending, the state is `error` with that error, and `flush` returns false.
  - **Other errors:** the batch is re-queued, with state `error`.

- [ ] **Step 1: Write the failing tests:**
  - `debounces changes into one save of only the changed fields`
  - `newest value wins and a change during a save goes in the next save` (assert that `save` never overlaps)
  - `offline keeps the batch under newer changes`
  - `retries once without the fields the server rejected` (Review Focus 2): it is called twice, the second call lacks the bad field, `pending` holds only it, and `flush` resolves false
  - `dispose sends what is pending` (Review Focus 3)
  - `mergeSaved keeps typing done during the save`
- [ ] **Step 2:** `yarn test`. Expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** `yarn typecheck && yarn lint && yarn test`. Expect PASS.
- [ ] **Step 5:** Commit `feat(v2): autosave queue for form answers`.

---

### Task 4: Field plug-ins (all but files and signature) and their registry

**Files:**
- Create: `forms/fields/index.ts`, `fields/convert.ts`, `fields/basic.tsx`, `fields/choice.tsx`, `fields/table.tsx`
- Modify: `forms/logic.ts` (`checkComplete`, `progress`)
- Test: `forms/fields/fields.test.ts`, `forms/logic.test.ts`

Reuse v1's `CheckRow`, `Segmented`, `RadioList` (`components/form/controls.tsx`) and the `field-input` classes. The table plug-in uses the same look as v1 `TableField` (fixed rows as a grid, free rows with add and remove), but draws its cells through the column type's plug-in with `compact`.

**Interfaces (Produces, `fields/index.ts`):**
```ts
export type RenderMode = "fill" | "readonly" | "preview";
export type RenderContext = {
  mode: RenderMode;
  values: Record<string, unknown>;                                // context values (job), or sample values in Preview
  upload?: (file: Blob, filename: string) => Promise<string>;     // private file URL; absent in readonly/preview
};
export type FieldInputProps = {
  field: FieldDef | ColumnDef; value: unknown; disabled: boolean; invalid: boolean;
  inputId: string; describedBy?: string; compact?: boolean; ctx: RenderContext;
  onChange: (value: unknown) => void;
};
export type FieldPlugin = {
  type: string; label: string; icon: Icon;                      // Icon from lib/cards; Plan 5's palette uses label + icon
  hasValue: boolean; inTable: boolean; labelable: boolean;      // labelable: a native control for <label for>
  defaultConfig: Record<string, unknown>;                       // Plan 5's "new field" settings
  isEmpty: (value: unknown) => boolean;                         // as each server plug-in's is_empty
  problems: (value: unknown, field: FieldDef) => FormError[];   // as each server plug-in's validate
  Input: ComponentType<FieldInputProps>;
};
export const FIELD_TYPES: FieldPlugin[];
export function getPlugin(type: string): FieldPlugin;           // unknown type -> UNKNOWN_PLUGIN (hasValue false, Input shows a placeholder)
```
Plan 5 adds a `Settings` component to `FieldPlugin`. Nothing in this plan reads one.

**Added to `forms/logic.ts`:**
- `checkComplete(def, answers): FormError[]` copies `check_complete`. For each visible field whose plug-in `hasValue`, it checks:
  - required or required-when and empty (by the plug-in's `isEmpty`) → "This field is required"
  - `must_tick` and not `true` → "This box must be ticked"
  - required table columns per row → `{field: <column id>, row: <_row>, message: "This field is required"}`
  - the plug-in's `problems(value, field)`, run on non-empty values (and on `[]` for tables)
- `progress(def, answers): number` (0 to 1) counts the visible fields that are required (or required-when), have `must_tick`, or are tables with `min_rows > 0` or `fixed_rows`. A field is done when `checkComplete` gives no error for it, or for one of its columns. Returns 1 when nothing counts.

**`fields/convert.ts`:**
- `textFromInput(s: string): string | null`
- `numberFromInput(s: string, decimal: boolean): number | null`: `""`, `"-"` or anything that isn't a number gives null, and whole numbers are rounded only when `decimal === false`
- `timeToInput(v: unknown): string` and `timeFromInput(s: string): string | null`: `"08:30"` becomes `"08:30:00"`
- `datetimeToInput(v: unknown): string` and `datetimeFromInput(s: string): string | null`: `"2026-11-08T08:30"` becomes `"2026-11-08 08:30:00"`
- `dateFromInput(s: string): string | null`

**Per type:**
- `text` sets `maxLength` from `max_length` (default 140).
- `long_text` uses a textarea.
- `number` takes `step` and `min`/`max` from its config.
- `checkbox` is a `CheckRow` that sends `true`/`false`.
- `yes_no` is a `Segmented` with Yes and No.
- `date`, `time` and `datetime` use native inputs.
- `info` shows `config.text` as plain text with `whitespace-pre-line`. It is never rendered as HTML.
- `choice`: with `display: "buttons"` it shows a `Segmented` when there are at most 3 short options, and a `RadioList` otherwise. As a drop-down it is a `select`. With `allow_other`, an "Other" choice reveals a text input whose value is `{"other": text}`.
- `multi_check` is a `CheckRow` list, plus an "Other" text when `allow_other`.
- `table`:
  - Fixed rows keep their labels: the `fixed_rows.column` cell is read-only, and rows cannot be added or removed.
  - Free rows add a row with `_row: newRowId()`.
  - A hint shows `min_rows`.
- `problems()` per type copies its server plug-in: `number` min/max, `multi_check` min_selected, and `table` min_rows plus fixed labels plus cell `problems` with `row`.

- [ ] **Step 1: Write the failing tests:**
  - `registry has every server type except files ones`: `FIELD_TYPES.map(p => p.type)` contains `text, long_text, number, currency, checkbox, yes_no, date, time, datetime, info, choice, multi_check, table`. Task 5 extends the list to the 16 types.
  - `conversions produce the server's shapes` (Review Focus 4), table-driven:
    - `textFromInput("")` gives null
    - `numberFromInput("3", false)` gives 3, and `numberFromInput("-", true)` gives null
    - `timeFromInput("08:30")` gives `"08:30:00"`, and `timeFromInput("")` gives null
    - `datetimeFromInput("2026-11-08T08:30")` gives `"2026-11-08 08:30:00"`
    - `timeToInput("08:30:00")` gives `"08:30"`
  - `isEmpty matches the server`:
    - text `""` and `null` are empty
    - checkbox `false` is not empty
    - multi_check `{selected: [], other: null}` is empty
    - table `[]` is empty
    - choice `{other: "x"}` is not empty
  - `problems match the server messages`: number below min gives `"Must be at least 1"`; table with fixed labels out of order gives `"Rows must match the fixed row labels"`; table min_rows 2 with 1 row gives `"Add at least 2 rows"`.
  - `only allowed column types are inTable`: true exactly for `text, long_text, number, checkbox, yes_no, choice, date, time`.
  - `getPlugin of an unknown type is the placeholder`: `hasValue` false.
  - In `logic.test.ts`, `checkComplete mirrors the server`. Each of these gives the server's exact message:
    - a required empty text
    - a required checkbox answered `false` gives **no** error (the server counts `false` as an answer)
    - a `must_tick` box answered `false`
    - `multi_check` `min_selected 2` with one ticked
    - a required table column empty in row `r_b`, which gives `{field: col, row: "r_b"}`
    - a field hidden by its rule gives no error
  - In `logic.test.ts`, `progress counts required visible fields only`: 0.5 with one of two answered, and 1 for a form with no required fields.
- [ ] **Step 2:** `yarn test`. Expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** `yarn typecheck && yarn lint && yarn test`. Expect PASS.
- [ ] **Step 5:** Commit `feat(v2): field plug-ins for the technician screen`.

---

### Task 5: Photos, files, signature, documents and the FormRenderer

**Files:**
- Create: `fields/files.tsx`, `fields/signature.tsx`, `forms/references.ts`, `forms/FormRenderer.tsx`
- Modify:
  - `fields/index.ts` (register the three types)
  - `lib/image.ts` (`dataUrlToBlob`)
  - `lib/pdf.ts` (`isPdf`)
  - `components/form/DocumentsDock.tsx` (prop type)
- Test: `forms/FormRenderer.test.tsx`, `forms/references.test.ts`, `lib/pdf.test.ts`, `fields/fields.test.ts`

**Interfaces:**
- Consumes: Tasks 2 and 4. v1 `SignaturePad`, `resizeImage`, `ReferenceCard`, `DocumentsDock`.
- `photos` and `files`:
  - Look and behaviour as v1 `FilesField`: grid or list, drag and drop, and a hint like "{count} of {min} minimum".
  - Each upload calls `ctx.upload(blob, name)` and appends `{file: url, caption: null}`. Photos are resized with `resizeImage` first.
  - A caption input per item when `captions` is set.
  - The add button is hidden once `max` is reached. `files` passes `accept` from `extensions`.
  - With no `ctx.upload` (preview), items keep a local `URL.createObjectURL` URL and the hint reads "Uploads are off in preview". Such a value is never sent anywhere, because preview has no queue.
- `signature`:
  - Reuses `SignaturePad` with `value = answer?.file ?? null`.
  - At the end of a stroke: `dataUrlToBlob(dataUrl)`, then `ctx.upload(blob, "signature-<field id>.png")`, then `onChange({file: url})`. Clearing sends `null`. In preview it keeps `{file: dataUrl}`.
  - Under the pad: "Signed by {signer} · {signed_at formatted en-GB}" when `signer` is set.
- `lib/image.ts`: `dataUrlToBlob(dataUrl: string): Blob`.
- `lib/pdf.ts`: `isPdf(url)` is also true when the URL's `file` query parameter ends in `.pdf` (the `reference_file` URL).
- `forms/references.ts`: `toDocuments(refs: ScreenReference[], def: Definition): { references: Reference[]; sections: { name: string; label: string }[] }`, for v1 `DocumentsDock`:
  - one `Reference` per `show_in` section id, with `section = id`
  - one with `section: null` when `show_in` is empty or names only fields
  - `sections` are `{name: s.id, label: s.title ?? ""}`

  `DocumentsDock`'s `sections` prop type is widened to `{ name: string; label: string }[]`. v1 callers still type-check.
- `forms/FormRenderer.tsx`:
  ```ts
  export type FormRendererProps = {
    definition: Definition; answers: Answers; ctx: RenderContext;
    errors?: Map<string, string>; references?: ScreenReference[];
    onChange?: (fieldId: string, value: unknown) => void;
  };
  export function FormRenderer(props: FormRendererProps): JSX.Element;
  ```
  - **Sections:** each visible section is a step in v1's look: `id="s-<section id>"`, a number `01`, the title and description, and its section `ReferenceCard`s.
  - **Fields:** `id="f-<field id>"`. Each has its label (with the brand `*` when `isRequired` and the mode isn't `readonly`), its `help`, the plug-in `Input`, the field's `ReferenceCard`s (references whose `show_in` holds the field id), and an error line from `errors`. Consecutive checkboxes are grouped as in v1 `groupSteps`.
  - **Disabled:** a field is disabled when the mode is `readonly`, or when `fill_from.locked`. A locked field shows "From the job".
  - **Values:** they come from `displayValue`.
  - **Unknown types:** a field of an unknown type shows the placeholder "This field type is not supported in the app yet." and the rest of the form renders.
  - **No side effects:** the renderer never calls the network itself.

- [ ] **Step 1: Write the failing tests** (`renderToStaticMarkup`; one fixture definition with one field of each of the 16 types):
  - `registry has all 16 server types`: the Task 4 list plus `photos, files, signature`.
  - `renders every type in fill and readonly`: no throw, and each field's label appears.
  - `readonly renders no enabled input`: the markup has no `<input`, `<textarea` or `<select` without `disabled`.
  - `locked fill_from field is disabled and says From the job`.
  - `hidden section is not rendered`.
  - `unknown type renders a placeholder` (Review Focus 5): a field `type: "rating"` gives the placeholder text, and the next field still renders.
  - `info text is not HTML`: `config.text = "<b>x</b>"` appears escaped.
  - `preview shows context values for fill_from fields`.
  - `toDocuments` cases: a section reference, a field-only reference (null), and a top reference.
  - `isPdf recognises reference_file URLs`.
- [ ] **Step 2:** `yarn test`. Expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** `yarn typecheck && yarn lint && yarn test`. Expect PASS.
- [ ] **Step 5:** Commit `feat(v2): form renderer with files, signatures and documents`.

---

### Task 6: Form screen page

**Files:** Create `pages/Submission.tsx`. Modify `App.tsx` (route `/s/:name` inside `AppShell`) and `lib/form.ts` (`submissionPath(name)`). Test: `forms/logic.test.ts` (`screenHeader`).

**Interfaces:**
- Consumes: `forms_core.api.get_submission` (GET), `save_answers` and `submit` (POST), and `uploadPrivateFile(blob, name, "Form Submission", name)` from `lib/api.ts`. Tasks 2 to 5.
- Produces:
  - `submissionPath(name: string): string`, which is `/s/<encoded>`.
  - `screenHeader(values: Record<string, unknown>): { customer: string | null; machine: string | null; serial: string | null; technician: string | null }`, in `logic.ts`. `machine` is `item_name ?? item_code`.
- Page behaviour (in v1 `Form.tsx`'s layout):
  - **Top bar:** `TopBar` with the form title. The subtitle is `"<name> · <customer>"`. Back goes to `/job/<context_name>` when `context_doctype === "DeployOps Job"`, and to `/` otherwise. A `SaveIndicator` and the progress bar show when the form is editable.
  - **Header:** eyebrow `"<name> · Form v<version_no>"`, then the title, then the `Meta` grid from `screenHeader`.
  - **Banners:**
    - Submitted: "Submitted on {date} by {name}. This form is locked."
    - Cancelled: "This form was cancelled."
    - Amended: "This form amends {amended_from}."
    - Offline and save-error banners, as in v1.
    - "{n} answers still needed."
    - Each of `general`.
  - **Editable** means `can_write && docstatus === 0`. The renderer gets `mode: "fill"` and `upload` when editable, and `mode: "readonly"` without upload otherwise.
  - **Saving:** one `AnswerQueue` per loaded submission. `save` posts `forms_core.api.save_answers` with `{name, changes}`, and `fieldOf` is `topFieldOf(def, ·)`. `onSaved` sets the values to `mergeSaved(server, pending)`. A `form_errors` error is shown on its fields with `errorsByField`.
  - **Fixed rows:** after load, and after every change, each entry of `fixedRowSeeds(def, values)` is queued and applied.
  - **Leaving:** `pagehide` and unmount call `queue.dispose()`. `beforeunload` asks the browser to confirm while `queue.pending` isn't empty.
  - **Submit** (shown only with `can_submit`):
    1. `flush`.
    2. `checkComplete`. With errors, show them and scroll to the first `f-`/`s-` id.
    3. Otherwise the confirm dialog, then post `forms_core.api.submit`.
    4. A refusal with `formErrors` shows them on the fields. Any other error goes in the dialog. Success reloads the page and scrolls to the top.
  - **Documents:** a `DocumentsDock` with `toDocuments(references, definition)`, raised when editable.

- [ ] **Step 1: Write the failing test:** `screenHeader picks the job values`, including `item_code` when there is no `item_name`, and nulls for missing keys.
- [ ] **Step 2:** `yarn test`. Expect FAIL.
- [ ] **Step 3:** Implement the page and the route.
- [ ] **Step 4:** `yarn typecheck && yarn lint && yarn test`. Expect PASS.
- [ ] **Step 5:** Commit `feat(v2): technician form screen`.

---

### Task 7: Machine forms on the job screen (server flags and UI)

**Files:**
- Modify: `deployops/api/forms.py` (`machine_forms`: two keys per entry), `pages/Job.tsx`, `lib/types.ts` (`Machine.uses_forms`)
- Create: `components/MachineForms.tsx`, `forms/machine.ts`
- Test: `deployops/tests/test_forms_screen.py` (new, `FormJobCase`) and `forms/machine.test.ts`

**Interfaces:**
- Server, additive. Each `machine_forms` entry gains:
  - `can_discard: bool`: status `Draft`, `"x"` in `_letters(job.assigned_technician, user)`, and the job status not in `CLOSED`.
  - `can_cancel: bool`: status `Submitted`, `"x"` in letters, and the job status not in `CLOSED`.
- `forms/machine.ts`: `formButtons(entry: MachineFormEntry): { primary: "start" | "continue" | "view" | null; remove: boolean; discard: boolean; cancel: boolean }`.
  - `start` when `can_start`.
  - `continue` when the status is Draft and there is a `submission`.
  - `view` when the status is Submitted, or when it is Not started with a (cancelled) `submission` and no `can_start`.
  - The other three come from `can_remove`, `can_discard` and `can_cancel`.
- `components/MachineForms.tsx`: `MachineForms({ job, row, onChange }: { job: string; row: string; onChange: () => void })`.
  - Loads `deployops.api.forms.machine_forms` (GET) with `useApi`.
  - **Each form** is a row in v1's checklist-link style: a status circle (green tick when Submitted, dashed when Not started, half-filled when Draft), the title, a "Required" or "Optional" chip, and "Flagged for review" when `flagged`.
  - **Start** posts `start_machine_form` with `{job, row, form}`, then navigates to `submissionPath(submission)`. Continue and View are links.
  - **Remove, Discard and Cancel** use `ActionDialog`. Remove needs a reason when `remove_needs_manager`, and posts `override_machine_forms` with `{job, row, remove: [form], reason}` (a JSON list, never a bare string). Discard and Cancel need a reason and post `discard_machine_form` / `cancel_machine_form` with `{submission, reason}`.
  - **"Add a form"** shows when `can_add && addable.length`. It opens a `Dialog` with a select of `addable`, a "Required" `CheckRow` and an optional reason, then posts `override_machine_forms` with `{job, row, add: [form], required: 0|1, reason}`.
  - **After any action:** reload, then call `onChange()`, because the machine status can change.
  - **Refusals:** a `ValidationError` from `can_start` (for example "This form is not planned for this machine.") is shown in a `Banner` under the list.
- `pages/Job.tsx` `MachineRow`: when `machine.uses_forms`, it renders `<MachineForms>` in place of the v1 checklist link or Start button. v1 machines are unchanged.

- [ ] **Step 1: Write the failing tests:**
  - Python (`test_forms_screen.py`):
    - `test_manager_gets_discard_and_cancel_flags`: Draft, then Submitted, as the Manager.
    - `test_technician_gets_no_discard_or_cancel`.
    - `test_flags_off_on_closed_job`.
  - TS (`machine.test.ts`): `formButtons` for Not started with `can_start`, Draft, Submitted with `can_cancel`, and Not started after a cancel without `can_start`, which gives `view`.
- [ ] **Step 2:** Run `bench --site deployops.local run-tests --app deployops --module deployops.tests.test_forms_screen` and `yarn test`. Expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `test_forms_screen` and `test_forms_api`, then `yarn typecheck && yarn lint && yarn test`. Expect PASS.
- [ ] **Step 5:** Commit `feat(v2): machine forms on the job screen`.

---

### Task 8: Form cards on home, sidebar and overview

**Files:**
- Create: `pages/FormJobs.tsx` (`/f/:form`), `lib/useCards.ts`
- Modify:
  - `lib/cards.ts`, `lib/types.ts` (`Card.to?: string`, `Card.color?: string | null`)
  - `pages/Home.tsx`, `pages/Overview.tsx`, `components/AppShell.tsx`, `pages/CardJobs.tsx` (extract `JobList`)
  - `App.tsx` (the route)
- Test: `lib/cards.test.ts`

**Interfaces:**
- `lib/cards.ts`:
  - `formCardToCard(c: FormCard): Card`:
    - `id: "form:" + c.form`, `title`, `subtitle: c.subtitle ?? ""`
    - `job_type: c.job_types.join(", ")`, `product_line: ""`, `doctype: "Form Submission"`
    - `icon: c.icon ?? "clipboard-check"`, `color: c.color`
    - `open_jobs`, `attention`, `waiting`
    - `to: "/f/" + encodeURIComponent(c.form)`
  - `mergeCards(v1: Card[], v2: FormCard[]): Card[]`: the v1 cards in their order, then the v2 cards in server order.
  - `cardPath(card): string`: `card.to ?? "/c/" + card.id`.
  - `cardColor(card): string`: `CARD_COLORS[card.id]`, then `FORM_COLORS[card.color]`, then `DEFAULT_COLOR`.
  - `FORM_COLORS: Record<string, string>` covers `blue, emerald, violet, amber, teal, rose, zinc`, in the same tile style as `CARD_COLORS`. Plan 5's Card appearance tab offers exactly these names and the `ICONS` keys.
- `lib/useCards.ts`: `useCards(): { cards: Card[] | null; error: ApiError | null; loading: boolean; reload: () => Promise<void> }`.
  - Loads `deployops.api.technician.home` and `deployops.api.forms.form_cards` (both GET) in parallel and returns `mergeCards`.
  - `AppShell` (`ShellContext`) and `Home` use it in place of their `useApi("…home")`. `Home`, `Overview` and the sidebar use `cardPath` and `cardColor` in place of `/c/${card.id}` and `CARD_COLORS[card.id]`.
- `pages/FormJobs.tsx`:
  - Loads `deployops.api.forms.form_jobs` with `{form}`.
  - Renders the shared `JobList`, extracted from `CardJobs` with no change in look. Each row adds "{outstanding} to do" and "{flagged} flagged" chips when they are not zero.

- [ ] **Step 1: Write the failing tests:**
  - `mergeCards keeps v1 first then v2 in server order`.
  - `formCardToCard maps the shape and path`.
  - `cardPath uses to for form cards and /c/ for v1`.
  - `cardColor falls back from v1 id to form colour to default`.
  - `summarize counts v2 cards too`.
- [ ] **Step 2:** `yarn test`. Expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** `yarn typecheck && yarn lint && yarn test`. Expect PASS.
- [ ] **Step 5:** Commit `feat(v2): form cards next to the checklists`.

---

### Task 9: Demo seed, build, migrate and manual test on test.site

**Files:** Create `deployops/tests/forms_demo.py`. Test: `deployops/tests/test_forms_screen.py` (`test_demo_seed`).

**Interfaces:**
- `seed(technician: str) -> dict` returns `{"form": str, "job": str, "rows": [str], "url": str}`. It is idempotent: a second run reuses everything and publishes nothing new. It doesn't commit; `bench execute` does.
- It uses `deployops.tests.erpnext_fixtures` helpers and `test_job.make_job`, with demo names:
  - item `DEMO-MACHINE` (serialized), serials `DEMO-SN-1` and `DEMO-SN-2`
  - category `Demo Equipment`, holding `DEMO-MACHINE`
  - customer `Demo Customer`, with a contact and an address
- **Form:** key `demo-all-fields`, `context_doctype = "DeployOps Job"`, with fixed ids (`s_demo01…`, `f_demo01…`), so a re-run has the same hash. Publish only when the Form has no `current_version`. The definition uses all 16 types:
  - **Section "Machine":**
    - `serial` (text, `fill_from serial_no` locked)
    - `customer` (text, `fill_from customer_name`, editable)
    - an `info` note
  - **Section "Checks":**
    - `area_safe` (checkbox, `must_tick`)
    - `power` (yes_no, required, outcome `block_machine` when No)
    - `no_power_reason` (long_text, `required_when` power = No)
    - `mounting` (choice, buttons, `allow_other`)
    - `accessories` (multi_check, `min_selected 1`, `allow_other`)
    - `cables` (number, `decimal false`, min 0, max 10)
    - `deposit` (currency)
    - `install_date` (date), `start_time` (time), `finished_at` (datetime)
  - **Section "Opening hours"** (shown when power = Yes):
    - `hours` (table, columns day text / open time / close time / closed checkbox, `fixed_rows` Mon to Sun)
    - `trainees` (table, columns name text required / role choice, `min_rows 1`)
  - **Section "Evidence":**
    - `photos` (photos, min 1, captions)
    - `documents` (files, extensions `["pdf"]`)
    - `customer_signer` (text, required)
    - `customer_signature` (signature, `signer_from` = customer_signer's id)
    - `technician_signature` (signature, `signer_from: "context:technician"`)
- **Rule:** Installation + `Demo Equipment` → the form, required.
- **Job:**
  - A submitted Delivery Note for `Demo Customer` with both serials, then `make_job("Delivery Note", note, assigned_technician=technician)`.
  - Then `frappe.db.set_value("DeployOps Job", job, "status", "On Site")`. This is a demo shortcut, as in the tests; the workflow history is skipped on purpose.
- **Technician:** the technician gets an Equipment Access Profile containing `Demo Equipment`. Their profile is created if missing, and the category is added if absent.
- **Return value:** `url` is `http://localhost:8004/deployops/job/<job>`.

- [ ] **Step 1: Write the failing test** `test_demo_seed` (on deployops.local, rolled back by `FormJobCase`):
  - Seed with `self.technician`.
  - The definition's types equal `set(forms_core.field_types.all_types())`.
  - The job has one active required row per machine for the demo form.
  - As the technician, `start_machine_form`, then `forms_core.api.get_submission`, gives the serial filled.
  - A second `seed` returns the same `form` and `job` and publishes no new Form Version.
- [ ] **Step 2:** Run `--module deployops.tests.test_forms_screen`. Expect FAIL.
- [ ] **Step 3:** Implement `seed`.
- [ ] **Step 4:** Run the whole suite and the checks:
  ```bash
  cd /home/kimbi/frappe/massarie_project
  bench --site deployops.local run-tests --app deployops
  bench --site deployops.local run-tests --app forms_core
  cd apps/deployops && ruff check deployops && ruff format --check deployops
  cd frontend && yarn typecheck && yarn lint && yarn test
  ```
  Expect all to pass, with forms_core's known failures (if any) listed as in Task 1.
- [ ] **Step 5:** Build, migrate and seed test.site:
  ```bash
  cd /home/kimbi/frappe/massarie_project/apps/deployops/frontend && yarn build
  cd /home/kimbi/frappe/massarie_project
  bench --site deployops.local migrate && bench --site test.site migrate
  bench --site test.site clear-cache && bench --site test.site clear-website-cache
  bench --site test.site execute deployops.tests.forms_demo.seed --kwargs "{'technician': '<technician email on test.site>'}"
  ```
  Expected:
  - `yarn build` writes `deployops/public/frontend/` and copies `deployops/www/deployops.html`.
  - `execute` prints the dict with `url`.
  - If `bench start` is not running, start it. Python changes need its reload, or a restart.
- [ ] **Step 6: Manual test script** (record each result in the task report; don't claim a step that wasn't run):
  1. **Home.** Open `http://localhost:8004/deployops` as the technician. A "Demo all fields" card appears after the v1 cards with 1 open job, and the same entry appears in the sidebar.
  2. **Job list.** Open the card: the demo job is listed with "2 to do". Open the job: each machine shows the demo form as Required / Not started, with Start.
  3. **Start.** Start the form on machine 1. The screen shows the serial `DEMO-SN-1`, locked, with "From the job", and the customer prefilled and editable.
  4. **Show-when.** Answer power = No: "Opening hours" disappears and the reason becomes required. Switch back to Yes: the opening-hours grid shows Mon to Sun.
  5. **Autosave.** Fill a few answers, wait for "Saved", and reload: the answers are kept. Type a password-like text such as `password: abc123` into a text field: that field shows the server's message, and the other answers still save.
  6. **Files and signatures.** Add a photo with a caption, and a PDF. A `.txt` file is refused on submit with "File type .txt is not allowed". Sign both signatures: after "Saved", the customer one shows "Signed by <customer signer>", and the technician one shows the technician's name.
  7. **Submit.** Press Submit with something missing: the count banner appears and the screen scrolls to the first problem. Fix it, then submit. The page shows the Submitted banner and is read-only.
  8. **Machine status.** Back on the job, machine 1's form is Submitted and machine 2's is still Not started. Completing machine 2 is refused until its form is submitted.
  9. **Blocking outcome.** On machine 2, submit with power = No (the reason filled). The machine becomes Blocked.
  10. **Manager actions** (optional). As a DeployOps Manager: Cancel machine 1's form with a reason, Start it again (an amendment opens with the answers kept), and Discard that draft with a reason. The job's Status Log has `form: cancelled` and `form: draft discarded`.
- [ ] **Step 7:** Commit `feat(v2): demo job form seed for test.site`. Don't commit the build output if `deployops/public/frontend` is git-ignored. Check with `git status` before adding.
