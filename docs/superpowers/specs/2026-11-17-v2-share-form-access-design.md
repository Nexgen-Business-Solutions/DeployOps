# Share form access: public links, "fill once", restricted audiences

Status: draft for owner approval (2026-11-17).

## Intent

A share form is a form with no context (not attached to a job), filled from its link `/deployops/f/<form>`.
The owner wants share forms to work like Jotform: open to anyone with the link, or limited to chosen
people or groups, and optionally filled only once per person or device. forms_core is the engine and
must stay usable by other customers, so all of this lives in forms_core; DeployOps only hosts the page.

### Today

- Every share form needs a login. `entries.fill_info` refuses Guest; `permissions.can_start_without_context`
  allows designers plus the roles in the `forms_core_no_context_roles` hook (DeployOps: Technician, Supervisor).
- A person can submit any number of entries.
- The fill page is the React route `/f/:form` (`frontend/src/pages/FillForm.tsx`) inside the signed-in app.

## Goals

1. **Audience**, set per share form, exactly one of:
   - **Public**: anyone with the link, no login.
   - **Roles**: signed-in users holding any of the selected roles (several allowed).
   - **Users**: the selected users only (several allowed).
   Roles and Users are never mixed on one form (owner decision).
2. **Entry limit**, set per share form: **Multiple** or **Once**.
   - Restricted forms (Roles/Users): Once = one submitted entry per user account. Exact.
   - Public forms: Once = one submitted entry per device, recognised by a browser ID plus a device
     fingerprint (owner decision: "same browser + fingerprint").
3. Examples the owner gave and how they map:
   employees, technicians, managers → roles; departments (accounting…) → one role per department;
   customers → the Customer role (customers need a portal user account to sign in); "John Doe" → Users.

## Non-goals

- Mixing roles and users on one form.
- Department access through the HR app's Department DocType.
- Captcha, email verification, payment or any paid service. The fingerprint is our own code, free.
- Changing job-attached (context) forms. They keep their current rules.

## Anti-goals

- A public form must not expose any other data: no job, customer, user or other submission data
  reaches a guest. Guests may read only the published definition of a public form and its documents
  marked for the fill page.
- The raw fingerprint traits are never stored or logged. Only a keyed hash.
- A wrongly blocked visitor must see a clear message, not an error page.

## Constraints

- forms_core stays host-agnostic: no DeployOps names, roles or routes inside it.
- Server-side enforcement, deny by default (AGENTS.md). The page hiding a button is never the check.
- Frappe/ERPNext v16, Python 3.14. Tests on deployops.local.
- No new paid or licence-restricted dependency.

## Approaches

**Fingerprint**
- **A. Own fingerprint (chosen).** A random browser ID in localStorage and a cookie, plus a hash of
  device traits (screen size and pixel ratio, OS/platform, timezone, language, CPU cores, device
  memory, GPU renderer via WebGL, a canvas render, a short list of installed fonts). No dependency,
  no cost.
- B. FingerprintJS open source: its free version only identifies a browser, so it adds little over A.
- C. A paid fingerprint service: costs money and sends visitor data to a third party. Rejected.

**Public page**
- **A. Inside the existing app (chosen).** `/deployops/f/<form>` becomes reachable without login and
  reuses `FormRenderer`, controls and uploads, so one renderer serves every form.
- B. A separate Frappe web page: a second renderer to keep in sync. Rejected.

## Design

### Data (forms_core)

On **Form** (settings, not part of the versioned definition, so changing them takes effect at once):
- `audience`: Select `Public` / `Roles` / `Users`. Default for new share forms: `Roles`, pre-filled
  with the host's `forms_core_no_context_roles` (DeployOps: Technician, Supervisor), so today's
  behaviour is the default.
- `audience_roles`: child table (Role link).
- `audience_users`: child table (User link).
- `entry_limit`: Select `Multiple` / `Once`. Default `Multiple`.
- Only meaningful when `context_doctype` is empty; hidden and ignored for job forms.

On **Form Submission**:
- `browser_key`, `device_key`: Data, indexed, hidden. Keyed hashes, set on public submissions only.
- Guest submissions have owner `Guest`; `submitted_by` empty.

Migration (patch): every existing share form gets `audience = Roles` with the hook roles and
`entry_limit = Multiple`. Nothing changes for current users.

Validation: `Roles` needs at least one role, `Users` at least one user. Roles `Guest` and
`Administrator` can't be chosen. Selected users must be enabled.

### Who may fill (server)

One function replaces `can_start_without_context`: `can_fill(form, user) -> reason | None`.
- Designers may always fill (to test).
- Public: anyone, Guest included.
- Roles: signed-in user with any selected role.
- Users: signed-in user in the list.
- Once: restricted → refuse if the user has a submitted entry on this form;
  public → refuse if a submitted entry has the same `browser_key` **or** `device_key`.
`fill_info`, `start_submission`, `save_answers`, `submit` and uploads all go through it.

What counts for Once (my calls):
- Only **submitted** entries (docstatus 1) count. Drafts and cancelled entries don't, so cancelling
  frees the slot, and amending (cancel, then the new amended entry) is allowed.
- Entries made before a form was switched from Multiple to Once count.
- Designers are exempt from Once, so they can test.
- A **signed-in** user on a **Public** form uses the signed-in flow (server drafts), and Once checks
  both their account and their device keys.

Who sees the entries: designers only, through the existing Entries tab, as today for share forms.
Guest entries are never readable through the owner rule: `submission_has_permission` and
`submission_query_conditions` must not treat `owner == "Guest"` as ownership (today
`stored.owner == user` would let any guest session read any guest entry).

### Public (guest) flow

- `fill_info` and the definition/document endpoints allow Guest **only** for Public forms.
- Guests don't get server drafts. Their answers are kept in the browser (localStorage) while they
  fill, then sent in one call: `submit_public(form, answers, browser_id, device_hash)`, which
  validates against the current version, creates and submits the entry atomically.
- Guest uploads: `upload_public(form, field)` stores a private File not yet attached, returns a
  token; `submit_public` attaches the files it references. Unattached guest files older than
  24 hours are deleted by a daily job.
- Limits (builder may tune): `submit_public` 10 per hour per IP; `upload_public` 30 per hour per IP;
  10 MB per file; file types limited to what the field allows, else images and PDF.
- Guests never see the "My entries" list. After submitting they see a thank-you screen.

### "Once" on public forms

- Browser: a random UUID stored in localStorage and a long-lived cookie (`fc_bid`); the device traits
  are hashed in the browser (SHA-256) into `device_hash`.
- Server: stores `HMAC(site secret, form + value)` for each, so keys can't be compared across forms
  or reversed. Raw traits never leave the browser.
- On open, `fill_info` takes the same two values and tells the page "already filled" up front.
- Honest limits, to show in the builder next to the setting: a private window or a different device
  gets through; two identical machines (same model, OS, browser, screen) can be blocked as one. It
  deters repeat entries; it is not proof of identity. For an exact limit, use Roles or Users.

### Builder (React)

The Publish/Share panel gets a **Who can fill** block:

```
Who can fill this form?
( ) Anyone with the link   – no login
( ) Roles  [Technician x] [Accounting x] [+]
( ) Users  [John Doe x] [Jane x] [+]

Entries per person
( ) As many as they like
( ) Only once   (public forms: per device – see note)

Link  https://<site>/deployops/f/<form>  [Copy]
```

Pickers search roles/users through a designer-only endpoint. Switching audience keeps the other
lists until saved.

### Fill page (React)

- `/f/:form` becomes a **bare fill route outside the session gate** (`App.tsx` today loads
  `technician.me`, which requires a DeployOps role, and `/f/:form` sits inside `AppShell`). The bare
  route has no nav or Home and serves guests, DeployOps users and other signed-in users (customers,
  accounting) alike; it calls only forms_core endpoints, never DeployOps ones.
- If the form is restricted and the visitor is a guest, send them to Frappe's `/login` with a
  redirect back to `/deployops/f/<form>`. This also covers Customer portal users, who otherwise have
  no DeployOps home page.
- Any signed-in user allowed by the audience gets server drafts and "My entries" (my call).
- Refusals show one clear message: "You've already filled this form", "This form is for selected
  people only", "This form is closed".
- Signed-in users keep server drafts and the "My entries" list as today.

## Tests

- Public form: guest can read and submit; guest can't read a Roles/Users form or any other data.
- Roles and Users: allowed, refused, user removed after starting.
- Once: second submit refused for the same user; for guests, same browser ID refused, same
  device hash with a new browser ID refused, different both allowed; drafts don't count.
- Rate limit and upload size/type refusals; unattached guest files cleaned up.
- Migration keeps existing forms on Roles with the hook roles.
- Frontend: guest fill flow, "already filled" screen, builder audience block.

## Left to the builder

- Exact trait list and canvas/WebGL code, as long as it's stable across reloads of the same browser.
- Endpoint names other than `can_fill`, `submit_public`, `upload_public`.
- Exact rate-limit numbers within the ranges above.
- Layout details of the builder block and refusal screens, following the existing builder kit.
