# v2 Plan 5: Form builder (implementation plan)

> **For agentic workers:** Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Administrators and Managers design, preview and publish forms in the React app. They no longer need to touch JSON in Desk.

**Architecture:**
- **Designer screens** live in `deployops/frontend` under `/builder`. They use the engine's existing builder API (`forms_core.api`).
- **Edits:** every edit to the definition goes through one reducer, which gives undo and redo for free.
- **Autosave** calls `save_draft` with the `modified` stamp the screen loaded. If the server refuses because someone else saved first, the screen shows "changed by X, reload".
- **Preview** reuses Plan 4's `FormRenderer` in `preview` mode.

**Tech:** React 19 + TS + Vite + Tailwind 4 (vitest, node env, `renderToStaticMarkup` for render tests). The spec calls for `@dnd-kit/core` and `@dnd-kit/sortable`, so they are the only new dependencies allowed.

**Spec:** `docs/superpowers/specs/2026-11-05-v2-form-builder-design.md`:
- §6 (screens, editing, publish, versions, documents, templates)
- §5.1 (each type's settings)
- §5.2 (rules language)
- §3.2 (definition JSON)

**Builds on:** Plan 1 (engine API), Plan 3 (Form Rules, provider `value_catalog`/`outcomes`) and Plan 4 (`src/forms/*`: types, logic, rules, FormRenderer, field plug-ins).

**Not in this plan:**
- Live co-editing (v3).
- Calculated fields (v2.x).
- The template gallery (Plan 7).
- PDFs (Plan 6).
- Phone editing: on phones the forms list is view-only.

## Global Constraints

- **Branch and commits:**
  - Repo `/home/kimbi/frappe/massarie_project/apps/deployops`, branch `task/v2-technician-screen`. Plan 4's uncommitted work is in the tree; keep building on top of it.
  - Commit locally per task if git is writable, with a short one-line message.
  - Stage explicit paths only. Never stage `.claude/worktrees/*` or `docs/superpowers/plans/*.md`.
  - Never push.
- **forms_core** (`../forms_core`, branch `task/v2-forms-core-reports`): change it only where Task 1 says.
- **Server checks stay authoritative:**
  - The client only helps. Publish errors come back as `form_errors` `[{field,row,message}]` and are shown on the field they name.
  - Designer rights are checked on the server (`forms_core_designer_roles` = DeployOps Manager and Administrator). The UI hides `/builder` from other users, but never relies on that for security.
- **Ids:** new sections, fields, table columns and option rows get ids from the client helper, in the same patterns as the server: `s_`, `f_`, `r_` plus 6 lowercase alphanumerics. The server rejects reused ids. Duplicating a field or section gives the copy new ids.
- **Only earlier fields** may be picked in Show when, Required when and Outcomes conditions. Earlier means earlier in section and field order.
- **Rules editor:** builds the JSON rules language exactly. Operators: `eq ne in not_in gt gte lt lte empty not_empty contains`. Groups: `all` / `any` / `not`, nested at most 4 deep. Labels:

  | Operator | Label |
  |---|---|
  | `eq` | is |
  | `ne` | is not |
  | `in` | is one of |
  | `not_in` | is not one of |
  | `gt` / `gte` | > / ≥ |
  | `lt` / `lte` | < / ≤ |
  | `empty` | is empty |
  | `not_empty` | is filled |
  | `contains` | contains |

- **Front-end checks:** `cd frontend && yarn typecheck && yarn lint && yarn test` all pass at the end of every task. Tabs, as in the existing files.
- **Layout:** laptop and tablet first, 1024px and wider. Below that, the builder shows "Open the builder on a larger screen" and the forms list is read-only.
- **Python:** ruff line-length 110, tabs. Messages go through `_()`. Tests run with `bench --site deployops.local run-tests --app <app> --module <module>`.

## Tasks

### Task 1: Server additions the builder needs (forms_core)
First check `forms_core/api.py`, `context.py` and `definition.py`. Add only what is missing, each with a test in `forms_core/tests/test_builder_api.py`:
- `create_form(title: str, context_doctype: str | None = None) -> str`: designers only. Creates a Form with an empty draft definition (one section) and returns its name.
- `designer_catalog(context_doctype: str | None) -> dict`:
  - Returns `{"field_types": [{"type", "label", "config_schema"}], "values": provider.value_catalog(), "outcomes": provider.outcomes()}`.
  - With no context, `values` and `outcomes` are empty.
  - Designers only.
- `publish_preview(form: str) -> dict`:
  - Runs every publish check without publishing.
  - Returns `{"errors": [...], "summary": {"added": [...], "removed": [...], "changed": [...]}, "drafts_on_older": {...}}`, using `versions.drafts_on_older`.
- `get_form` must return `modified` and `modified_by` (full name), so the screen can handle "changed by X, reload". Add them if they are missing.

### Task 2: Builder state: reducer, ids, undo/redo, autosave
- `src/builder/ids.ts`: `newId(prefix: "s"|"f"|"r"): string`.
- `src/builder/state.ts`: `type Action` covers add, move, duplicate and delete for sections and fields, `updateField`, `updateSection` and `setTitle`. `reduce(def, action) -> def` is pure. `History` provides `apply`, `undo`, `redo`, `canUndo` and `canRedo`.
  - Tests: duplicate makes new ids, including table column ids. Delete drops conditions that point at the deleted field and reports them. Undo and redo round-trip.
- `src/builder/autosave.ts`: saves 1 s after the last edit, one save at a time, and sends the latest `modified`.
  - A conflict reply sets state `conflict` with the server's `modified_by`.
  - Test: two quick edits make one save, and a conflict stops further saves.

### Task 3: Forms list and routes
- `/builder` (forms list):
  - Columns: Title, Status (Draft / Published / Archived), Current version, Rules using it (count of active DeployOps Form Rules), Last published.
  - Actions: New (asks for a title and creates a job form, `context_doctype` = `DeployOps Job`), Duplicate (export then import), Archive, Import (choose a JSON file), Export (download JSON).
- `/builder/:form` opens the builder.
- Add a Builder link to the AppShell sidebar for designers (session roles).
- Add a whitelisted DeployOps endpoint `deployops.api.forms.form_rule_counts() -> dict[str, int]`. It checks designer rights. Test it.

### Task 4: Three-panel builder
- **Left, palette:** the field types from `designer_catalog`. Click to add a field after the selected one, or drag it onto the form.
- **Middle, the form:** sections and fields.
  - Sections are steps, with a title.
  - Fields are dragged with `@dnd-kit` to reorder or move between sections, and work with the keyboard.
  - Each field and section has duplicate and delete. Deleting a field that conditions use asks for confirmation and lists them.
- **Right, settings for the selected field:**
  - Label, help text, `key` (slug, unique), required.
  - Show when, Required when.
  - The type's own settings (`config` keys per §5.1 / Plan 4's list): options editor, min/max, decimal, display, allow_other, columns for tables, fixed rows, `signer_from`, the `info` text, extensions, captions.
  - Fill from: a value from `designer_catalog.values`, plus locked or editable.
  - Outcomes: condition + effect from `designer_catalog.outcomes`.
  - Internal-only checkbox, for Plan 6.
- **Top bar:**
  - Title (editable).
  - "Draft saved" / "Saving…" / conflict banner.
  - Undo and Redo, with Ctrl+Z and Ctrl+Shift+Z.
  - Preview, Publish, Versions.
- **Tabs:** Form, Documents (attach reference files to the form; show each in a chosen section or field), Card appearance (subtitle, icon, colour, if the Form DocType has those fields; otherwise skip and note it), Used by (the Form Rules using it, with a Desk link).
- Tests: render tests for the settings panel per type (it shows that type's config inputs), and for the conditions editor (only earlier fields are offered, and it produces exact rule JSON).

### Task 5: Preview, publish, versions
- **Preview:**
  - `FormRenderer` in `preview` mode at phone, tablet or desktop width (375 / 768 / 1200px frame).
  - "Fill sample job" fills the context values with sample data from the catalog keys.
  - Nothing is saved.
- **Publish:**
  1. Calls `publish_preview`. Errors are listed and linked; clicking one selects that field and shows the message.
  2. The change summary shows added, removed and changed fields, and the warning "{n} drafts are on v{x} and will stay there unless moved up".
  3. Change note, then Publish.
- **Versions:**
  - A list of versions.
  - View one read-only (FormRenderer `readonly`).
  - Compare two (`compare_versions`), shown as added, removed and changed.
  - Restore as draft, after a confirmation.

### Task 6: Build, migrate, check on test.site
- Run `cd frontend && yarn build`.
- Run `bench --site deployops.local migrate && bench --site test.site migrate`.
- Run the full Python suite once for each app. Known pre-existing failures: 2 in `test_technician_api` (stale job DO-JOB-2026-00730).
- `curl -s -o /dev/null -w '%{http_code}' http://localhost:8004/deployops/builder` must print 200. If Redis or the web server isn't running, say so; don't start long-lived services.
- Manual test script: log in as a DeployOps Manager on test.site, then:
  1. New form.
  2. Add a yes_no field and a text field shown when it is "No".
  3. Preview.
  4. Publish.
  5. Add a Form Rule in Desk.
  6. Open the demo job form.
