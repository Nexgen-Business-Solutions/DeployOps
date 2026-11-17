# Share Form Access Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Share forms can be public (no login) or limited to chosen roles or users, and can be limited to one entry per person or device.

**Architecture:** All rules live in forms_core: new settings on Form, a single `can_fill` gate, guest endpoints for public forms, and keyed device hashes on Form Submission. DeployOps' React app gets a bare `/f/...` route outside the session gate, a free in-house browser fingerprint, a guest fill flow, and a "Who can fill" block in the builder.

**Tech Stack:** Frappe v16 / Python 3.14 (forms_core), React + TypeScript + Vitest (deployops/frontend).

**Spec:** `docs/superpowers/specs/2026-11-17-v2-share-form-access-design.md`

## Global Constraints

- forms_core stays host-agnostic: no DeployOps names, roles, routes or API calls inside it.
- Server-side enforcement, deny by default. A hidden button is never the check.
- Raw fingerprint traits are never sent, stored or logged; the server stores only `HMAC(site key, form + value)`.
- Guests can read only a Public form's published definition and its documents. Nothing else.
- No paid or licence-restricted dependency. The fingerprint is our own code.
- Tests run on `deployops.local`. After schema changes, `bench --site deployops.local migrate` and `bench --site test.site migrate`.
- Do **not** commit or push. Leave all changes uncommitted for the owner to review. Code for forms_core lives in `apps/forms_core`; DeployOps work goes on a task branch `task/v2-share-access` off `main-v2`.
- Python tests: `bench --site deployops.local run-tests --app forms_core --module <module>`. Frontend: `cd apps/deployops/frontend && yarn test && yarn lint`.

## Review Focus

1. A guest calling any existing endpoint (`get_submission`, `list_entries`, `reference_file`, `save_answers`) on a guest-owned entry: must be refused. Pinned in Task 2.
2. A form switched from Public to Users while a guest has the page open: `submit_public` must refuse. Pinned in Task 3.
3. A user removed from the Users list after starting a draft: `save_answers`/`submit` must refuse. Pinned in Task 2.
4. `submit_public` with a file token from another form, or a token already used: must refuse. Pinned in Task 3.
5. localStorage unavailable (private mode, blocked storage): the guest page still works; fingerprint falls back to cookie and device hash. Pinned in Task 5.

---

### Task 1: Share settings on Form and submission keys

**Files:**
- Create: `forms_core/forms_core/forms_core/doctype/form_audience_role/` (child table: `role` Link Role, reqd)
- Create: `forms_core/forms_core/forms_core/doctype/form_audience_user/` (child table: `user` Link User, reqd)
- Modify: `forms_core/forms_core/forms_core/doctype/form/form.json` and `form.py`
- Modify: `forms_core/forms_core/forms_core/doctype/form_submission/form_submission.json`
- Create: `forms_core/forms_core/patches/share_audience_defaults.py`; Modify: `forms_core/patches.txt` (`[post_model_sync]`)
- Test: `forms_core/forms_core/tests/test_share_settings.py`

**Interfaces:**
- Produces on Form: `audience` Select `Public\nRoles\nUsers` (default `Roles`), `audience_roles` Table (Form Audience Role), `audience_users` Table (Form Audience User), `entry_limit` Select `Multiple\nOnce` (default `Multiple`).
- Produces on Form Submission: `browser_key`, `device_key` (Data, hidden, read-only, `search_index: 1`).
- Produces in `forms_core/forms_core/share.py`: `default_roles() -> list[str]` (= `permissions.no_context_roles()`).

- [ ] **Step 1: Write failing tests** in `test_share_settings.py` (use `make_form`, `no_context_roles`, `make_role`, `make_user` from existing test utils):
  - `test_new_share_form_defaults`: a new Form with no context, hook roles `["FC Tech"]` → `audience == "Roles"`, roles `== ["FC Tech"]`, `entry_limit == "Multiple"`.
  - `test_roles_needs_a_role`: `audience="Roles"` with empty table → `frappe.ValidationError`.
  - `test_users_needs_a_user`: same for `Users`.
  - `test_guest_and_administrator_roles_refused`: role `Guest` or `Administrator` in `audience_roles` → `ValidationError`.
  - `test_disabled_user_refused`: disabled user in `audience_users` → `ValidationError`.
  - `test_other_list_cleared_on_save`: `audience="Roles"` with both tables filled → saved doc keeps roles, `audience_users == []`; `Public` clears both.
  - `test_job_form_ignores_settings`: form with `context_doctype` set saves with any audience and no lists.
  - `test_patch_sets_existing_forms`: a share form with empty `audience` → after `share_audience_defaults.execute()`, `Roles` with hook roles and `Multiple`.
- [ ] **Step 2: Run** `--module forms_core.tests.test_share_settings` → FAIL (fields missing).
- [ ] **Step 3: Implement.** Add the child DocTypes and fields (`depends_on: eval:!doc.context_doctype` for the four Form fields; `audience_roles` `depends_on: eval:doc.audience=='Roles'`, `audience_users` for `Users`). In `Form.validate`: fill default roles when new, Roles and table empty and no context; clear the unused list; raise for empty list, Guest/Administrator, disabled users. Patch: for each Form with no context and empty `audience`, set `Roles` + default roles + `Multiple`, save with `ignore_permissions`.
- [ ] **Step 4: Migrate both sites, run the module** → PASS. Also run `test_form` and `test_install` → PASS.
- [ ] **Step 5: Stop for review** (no commit).

### Task 2: `can_fill` gate and the Guest-owner fix

**Files:**
- Modify: `forms_core/forms_core/share.py`
- Modify: `forms_core/forms_core/permissions.py` (replace `can_start_without_context` uses; fix owner checks)
- Modify: `forms_core/forms_core/entries.py` (`fill_info`), `forms_core/forms_core/submissions.py` (`start`, `save_answers`), `forms_core/forms_core/api.py` (`submit`)
- Test: `forms_core/forms_core/tests/test_share_access.py`; update `test_entries.py`, `test_filling_api.py` where they rely on the old gate.

**Interfaces:**
- Produces in `share.py`:
  - `device_keys(form: str, browser_id: str | None, device_hash: str | None) -> tuple[str | None, str | None]`: `hmac.new(get_encryption_key().encode(), f"{form}:{value}".encode(), sha256).hexdigest()`; `None` for empty input; inputs longer than 128 chars refused.
  - `can_fill(form: str, user: str, browser_key: str | None = None, device_key: str | None = None) -> str | None`: `None` = allowed, else the refusal message. Order: archived / unpublished / job form → existing messages; designer → `None`; audience check; then Once.
  - Messages (exact copy): `"Please sign in to fill this form."` (guest on Roles/Users), `"This form is for selected people only."`, `"You've already filled this form."`.
- Once counts submissions with `docstatus == 1` only. Restricted: `owner == user`. Public: `browser_key` match OR `device_key` match; a signed-in user on a Public Once form is checked by `owner` too.

- [ ] **Step 1: Write failing tests** in `test_share_access.py`:
  - `test_public_allows_guest`, `test_roles_allows_member_refuses_other`, `test_users_allows_listed_refuses_other`, `test_guest_on_restricted_asked_to_sign_in` (exact messages above).
  - `test_designer_bypasses_audience_and_once`.
  - `test_once_restricted_counts_only_submitted`: draft → allowed; submitted → `"You've already filled this form."`; cancel it → allowed again.
  - `test_once_counts_entries_from_before_switch`: submit under Multiple, switch to Once → refused.
  - `test_once_public_browser_or_device`: submitted guest entry with keys (b1, d1): (b1, d2) refused, (b2, d1) refused, (b2, d2) allowed.
  - `test_device_keys_differ_per_form_and_hide_input`: same input on two forms → different keys; key does not contain input.
  - `test_removed_user_cannot_save_or_submit`: user starts draft on Users form, is removed from the list → `save_answers` and `api.submit` raise `frappe.PermissionError`.
  - `test_guest_cannot_read_guest_entries`: a submission with `owner="Guest"`; as Guest, `frappe.has_permission("Form Submission", "read", doc)` is False and `frappe.get_list("Form Submission")` returns nothing.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** `can_start_without_context(user)` is removed; new no-context submissions in `submission_has_permission` use `can_fill(doc.form, user) is None`; stored no-context submissions: `stored.owner == user and user != "Guest"` plus designer, and for write/submit also `can_fill` without the Once check (pass a flag `check_once=False` — add it to the signature: `can_fill(..., check_once: bool = True)`). In `submission_query_conditions`, the own clause becomes `owner = <user>` only when user is not Guest, else `1=0`. `fill_info` uses `can_fill` and no longer throws for Guest (Task 3 extends its return).
- [ ] **Step 4: Run** `test_share_access`, `test_entries`, `test_filling_api`, `test_submissions`, `test_context` → PASS.
- [ ] **Step 5: Stop for review.**

### Task 3: Public (guest) endpoints

**Files:**
- Create: `forms_core/forms_core/public.py`
- Modify: `forms_core/forms_core/api.py` (whitelisted wrappers), `forms_core/forms_core/entries.py` (`fill_info`), `forms_core/forms_core/hooks.py` (daily job)
- Test: `forms_core/forms_core/tests/test_public.py`

**Interfaces** (all in `api.py`, `allow_guest=True`, delegating to `public.py`):
- `fill_info(form, browser_id=None, device_hash=None) -> dict`: existing keys plus `audience`, `entry_limit`, `login_required: bool` (guest on Roles/Users), and for a guest on Public: `definition`, `references` (`[{title, url, show_in}]`, url → `public_reference_file`). `mine` is `[]` for Guest.
- `public_reference_file(form, file)` (GET): serves a reference of the current version; Public forms only.
- `upload_public(form, field)` (POST multipart `file`) `-> {"token": str, "file_name": str}`: Public form only; field must be a file/photo/signature field of the current version; 10 MB max; extension must be allowed by the field config, else `jpg jpeg png webp heic pdf`. Stores a private File with `attached_to_doctype="Form"`, `attached_to_name=form`, `attached_to_field=f"fc_public:{field}"`; the token is the File's `name`. `submit_public` re-attaches used files to the new submission (so they stop matching the pending pattern). This keeps pending uploads in the database, not in the cache, so a cache flush can't orphan them.
- `submit_public(form, answers, browser_id, device_hash) -> {"name": str}` (POST): Guest **or** signed-in on a Public form. Runs `can_fill` with keys; replaces upload tokens in answers by file URLs (token must exist, match form and field, unused); creates the submission with `ignore_permissions`, sets keys, attaches files, submits — all in one transaction; deletes used tokens.
- Rate limits via `frappe.rate_limiter.rate_limit`: `submit_public` `limit=10, seconds=3600`; `upload_public` `limit=30, seconds=3600`.
- `public.cleanup_uploads() -> int`: deletes Files with `attached_to_doctype="Form"` and `attached_to_field like "fc_public:%"` created more than 24 h ago; returns the count. Added to `scheduler_events["daily"]`.

- [ ] **Step 1: Write failing tests** in `test_public.py` (as Guest via `frappe.set_user("Guest")`):
  - `test_guest_fill_info_public_has_definition`; `test_guest_fill_info_restricted_login_required_no_definition`.
  - `test_submit_public_creates_submitted_entry`: docstatus 1, owner Guest, keys set and not equal to inputs.
  - `test_submit_public_refused_after_switch_to_users`.
  - `test_submit_public_once_second_refused`.
  - `test_submit_public_validates_required_fields` (raises `FormValidationError`).
  - `test_upload_rejects_big_and_wrong_type`; `test_upload_refused_on_restricted_form`.
  - `test_token_from_other_form_or_reused_refused` (a token of another form, of another field, or already attached to a submission).
  - `test_pending_upload_not_served_as_reference`: `public_reference_file` refuses a pending upload's URL.
  - `test_guest_cannot_use_submission_endpoints`: `get_submission`, `save_answers`, `reference_file`, `list_entries` on the guest entry raise `frappe.PermissionError`.
  - `test_cleanup_removes_old_unused_files`.
  - `test_rate_limit_applied`: the two endpoints carry `rate_limit` (assert via a request-count loop with `frappe.local.request_ip` set, or by checking the wrapper attribute if Frappe exposes one).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** per the interfaces. Reuse `submissions.validate`/`check_complete` through the normal insert + submit path; set `doc.flags.forms_core_public = True` so `submission_has_permission` is not consulted (insert/submit with `ignore_permissions`).
- [ ] **Step 4: Run** `test_public` and the Task 2 modules → PASS.
- [ ] **Step 5: Stop for review.**

### Task 4: Designer endpoints for share settings

**Files:**
- Modify: `forms_core/forms_core/api.py`
- Test: `forms_core/forms_core/tests/test_builder_api.py`

**Interfaces:**
- `get_form` already returns `doc.as_dict()`, so the four fields come along. Nothing to add.
- `set_share_settings(form: str, audience: str, roles: list[str] | None = None, users: list[str] | None = None, entry_limit: str = "Multiple") -> dict` (POST, designer): saves through `Form.validate`; returns `{audience, roles, users: [{user, full_name}], entry_limit}`. Allowed on published forms.
- `search_audience(kind: str, txt: str = "") -> list[dict]` (designer): `kind="role"` → `[{value: role}]`, enabled roles, excluding `Guest`, `Administrator`, `All`; `kind="user"` → `[{value: name, label: full_name, email}]`, enabled users excluding Guest/Administrator; 20 results, `like %txt%` on name/full_name.

- [ ] **Step 1: Write failing tests**: `test_set_share_settings_roundtrip`, `test_set_share_settings_designer_only` (PermissionError for a non-designer), `test_search_audience_excludes_system_roles`, `test_search_audience_users`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS. **Step 5: Stop for review.**

### Task 5: Fingerprint and the bare fill route (frontend)

**Files:**
- Create: `deployops/frontend/src/lib/fingerprint.ts`, `fingerprint.test.ts`
- Modify: `deployops/frontend/src/App.tsx`
- Create: `deployops/frontend/src/pages/PublicFill.tsx`, `PublicFill.test.tsx`
- Modify: `deployops/frontend/src/pages/FillForm.tsx`, `deployops/frontend/src/pages/Submission.tsx` (prop `bare`)

**Interfaces:**
- `fingerprint.ts`:
  - `browserId(): string`: read `localStorage["fc_bid"]`, else cookie `fc_bid`, else `crypto.randomUUID()`; write both (cookie `max-age=31536000; path=/; SameSite=Lax`); every storage access in try/catch.
  - `deviceTraits(): string[]`: screen width×height, `devicePixelRatio`, `navigator.platform`, `Intl.DateTimeFormat().resolvedOptions().timeZone`, `navigator.language`, `hardwareConcurrency`, `deviceMemory`, WebGL `UNMASKED_RENDERER_WEBGL`, a canvas render data URL, and which of 20 common fonts measure differently from the fallback. Missing values become `""`.
  - `deviceHash(): Promise<string>`: SHA-256 hex (via `crypto.subtle`) of `deviceTraits().join("|")`.
- `App.tsx`: before calling `technician.me`, if `location.pathname` starts with `${APP_BASE}/f/`, render a separate router with `/f/:form` → `FillForm` and `/f/:form/entry/:name` → `Submission bare`. No `AppShell`, no `SessionContext`.
- `FillForm` calls `fill_info` with `browser_id` and `device_hash`. Then:
  - `login_required` → `window.location.assign("/login?redirect-to=" + encodeURIComponent(location.pathname))`.
  - Guest on Public → render `PublicFill`.
  - Signed-in → today's start/continue list, but start navigates to `/f/<form>/entry/<name>` and list links likewise.
- `PublicFill({info})`: renders `FormRenderer` in fill mode, keeps answers in `localStorage["fc_draft:<form>"]` (try/catch), uploads via `uploadTo("forms_core.api.upload_public", ...)` storing the returned token as the field value, submits with `submit_public`, then shows "Thank you, your answers were sent." and clears the draft. Refusals show `info.reason` in a warning banner.
- `Submission bare`: back link `/f/<form>`, no PDF button.

- [ ] **Step 1: Write failing tests**:
  - `fingerprint.test.ts`: `browserId` stable across two calls; survives `localStorage` throwing (mock `getItem`/`setItem` to throw) using the cookie; `deviceHash` is 64 hex chars and identical for identical traits.
  - `PublicFill.test.tsx`: draft restored from localStorage; submit posts `submit_public` with `browser_id` and `device_hash` and shows the thank-you text; works when localStorage throws; reason banner shown when `can_start` is false.
- [ ] **Step 2: Run** `yarn test` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `yarn test && yarn lint && yarn build` → PASS (existing 108 tests still pass).
- [ ] **Step 5: Stop for review.**

### Task 6: "Who can fill" in the builder

**Files:**
- Create: `deployops/frontend/src/builder/ShareSettings.tsx`, `ShareSettings.test.tsx`
- Modify: `deployops/frontend/src/builder/api.ts` (types and calls), `builder/Publish.tsx` (show the block on the "is live" screen of share forms), `builder/SettingsPanel.tsx` (same block for share forms at any time)

**Interfaces:**
- `api.ts`: extend `FormRecord` with `audience: "Public" | "Roles" | "Users"`, `audience_roles: {role: string}[]`, `audience_users: {user: string}[]`, `entry_limit: "Multiple" | "Once"`; add `saveShareSettings(form, s)` → `set_share_settings`, `searchAudience(kind, txt)` → `search_audience`.
- `ShareSettings({record, onSaved})`: three radio options (Anyone with the link – no login / Roles / Users), a multi-select chip picker for the chosen kind (search as you type), two radios for entries (As many as they like / Only once), the share link with Copy, and a note under "Only once" when Public: "On public forms, 'once' is per device. A private window or another device can get through, and identical machines may be treated as one." Saves on change; shows server errors inline.
- Publish's "is live" text changes from "Share this link with your team…" to text matching the audience (Public: "Anyone with this link can fill the form."; Roles/Users: "People you chose can fill the form after signing in.").

- [ ] **Step 1: Write failing tests**: switching to Users shows the user picker and hides roles; saving posts `set_share_settings` with `users` only; the "once" note shows only for Public; server error is displayed.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** `yarn test && yarn lint && yarn build` → PASS.
- [ ] **Step 5: Manual check** on test.site (localhost:8004): make a Public form, open the link in a private window and submit; submit again → "You've already filled this form."; switch to Users with tech1, open as a guest → login, then fill as tech1. **Stop for review.**
