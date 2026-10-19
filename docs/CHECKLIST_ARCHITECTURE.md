# DeployOps — Checklist Architecture (#20 / #41)

**Status:** one native DocType per checklist, decided by the owner on 2026-10-20 (product owner's recommendation). It replaces the earlier draft design of versioned templates on one engine, which was never committed. Field lists come from the live Jotforms and stay **pending #40 sign-off**.

## 1. Decision

| | **One DocType per checklist (chosen)** | Versioned templates (dropped) |
|---|---|---|
| Fields | Real typed columns, visible in Desk, reports and print formats | Answers stored as rows |
| Changing a question | Developer change and migration | Admin publishes a new version |
| History | Frappe version history on each form (`track_changes`) | Locked template versions |
| Reporting | Easy: one column per field | Harder |

AGENTS.md asks to avoid generic dynamic-form technology when product-specific DocTypes are more reliable. That is the reason for this choice.

## 2. Data model

| DocType | Naming | Card |
|---|---|---|
| DeployOps Cashmatic Pre-installation | `DO-CPI-.YYYY.-.#####` | Pre-installation · Cashmatic |
| DeployOps Cashmatic Installation | `DO-CIN-.YYYY.-.#####` | Installation · Cashmatic |
| DeployOps BellaBot Pre-installation | `DO-BPI-.YYYY.-.#####` | Pre-installation · BellaBot |
| DeployOps BellaBot Installation | `DO-BIN-.YYYY.-.#####` | Installation · BellaBot |
| DeployOps Cashmatic Maintenance | `DO-CMT-.YYYY.-.#####` | Maintenance · Cashmatic |

All five are submittable. They share a header (plus `form_version` and `submission_snapshot`, see §4) that is filled from the job when the form starts and cannot be changed afterwards: job, machine row, customer, address, Item, Serial No, technician and company.

Shared child tables:

| Child table | Used for |
|---|---|
| DeployOps Checklist Photo | Photo evidence: private image and caption |
| DeployOps Checklist File | Other files (maps, advertising media) |
| DeployOps Checklist Opening Hours | Fixed rows Monday to Sunday: open, close or closed |
| DeployOps Checklist Maintenance Task | Fixed task rows: completed Yes or No, remarks |
| DeployOps Checklist Trainee | BellaBot trainees |
| DeployOps Checklist Action | BellaBot commercial actions |

**Which form a machine uses:** the job type plus the **Checklist product line** (Cashmatic or BellaBot) of the equipment category that contains the machine's Item. This is a new field on DeployOps Equipment Category. A machine whose Item is in no category with a product line, or in categories with two different lines, has no checklist.

## 3. Rules

All rules live in `deployops/checklists/form.py` (`ChecklistForm`), and each DocType's controller only declares its own constants.

- **Starting a form:** the job must be in a working state and the machine must not be cancelled. The form must be the right one for the machine, and each machine row gets one live form.
- **Drafts save with gaps**, so the app can autosave. **Submit** checks everything:
  - Required fields, including Check boxes, which must be ticked.
  - Fields that are required only under a condition (`mandatory_depends_on`).
  - `ANY_OF`: tick at least one box in a section.
  - `MIN_ROWS`: for example, at least 3 installation photos.
  - Required columns in table rows.
  - Opening hours: each day needs times, or must be marked closed.
- **Conditions** support exactly one form, `eval:doc.<field>=='<value>'`. The server and the app read conditions the same way, and anything else is refused.
- **`FIXED_ROWS`** (opening hours, maintenance tasks) are created with the form, and their labels cannot change.
- **Evidence files** must be private files attached to the same form. Signatures must be PNG data URLs under 400 kB.
- **Secrets:** text that looks like a password, PIN, OTP or pairing code is refused in every text field and table cell.
- **Access:** each form is visible exactly when its job is (`form_query_conditions` and `form_has_permission`). Role rights are in the matrix (`deployops/security/matrix.py`). A Manager can cancel a submitted form, with a reason.

## 4. Versions and snapshots

- Each form class has a **`FORM_VERSION`**. A form records the version it was started on (`form_version`).
- On submit, the form saves a **`submission_snapshot`**: every section, question label, option and answer, as JSON. The app shows a submitted checklist from its snapshot, so it keeps the exact questions it was answered against even after the DocType changes. Frappe's change history (`track_changes`) still records every edit made while it was a draft.
- A draft started on an older version cannot be submitted; a Manager cancels it and a new one is started.

**Changing a form safely:**
1. Edit the DocType.
2. Bump `FORM_VERSION` in its controller.
3. Run `bench migrate` on a test site first.

- **Adding a field** is safe.
- **Removing a field** keeps its column and old data in the database, and old snapshots still show it.
- **Renaming a field** (fieldname) needs a data patch in `deployops/patches/` to copy the values, or old drafts lose that answer.

### Signatures (#21)
- Every form keeps a **Signature record** (child table `DeployOps Checklist Signature`), filled by the server only. For each signature it holds the signer's name, when it was signed and which user captured it.
- Each form's `SIGNERS` says where the signer's name comes from: a name field on the form (keys receiver, client representative, customer), or the job's technician.
- The time stays the same until the drawing itself changes, and the record is rebuilt on every save, so it can't be edited by hand.
- A signature without a signer name cannot be submitted.
- The snapshot includes the record, and the app shows "Signed by … · time" under each signature.
- BellaBot Installation got a **Customer name** field for its customer signature, which had none.

### Evidence files (#21)
Photos and files are private and attached to the form, so access to them follows the form, and the form follows the job. Tested: the assigned technician and a Supervisor in scope can open a file; another technician and Guest cannot.

### Not built (noted for a later decision)
- **Step exceptions** ("incomplete reasons" in #21): a technician marks a required step N/A or Blocked with a reason, instead of ticking it. Proposed: one shared table per form (step, status, reason, who, when). A step counts as answered if ticked or excepted, and Blocked steps are flagged for review. Held back by the owner on 2026-10-20.
- **Machine completion:** a machine can be marked Done on the job without a submitted checklist. Not part of #21's scope.

## 5. Mapping notes (pending #40 sign-off)

These differ from the Jotforms, either to keep a single source of truth or to fix source problems:

- Customer, machine, serial number, technician and address come from the job, not typed in again.
- Cashmatic Pre-installation: the Jotform "Device" dropdown (Self Pay 460, Visual Pay 27 wall mounted, …) is now read-only and filled from the machine's Item. The mounting and option part of those choices (wall mounted, with stand, coins drawer) is not captured separately yet; "Special installation request" covers mounting.
- Cashmatic Installation: "Type of network" and "IP" appeared three and two times; they are now once each. Unlabelled step groups were given the headings "Preparing the machine" and "Customer training". The typo "Codition" is fixed.
- POS brand and API connector are shown and required only when POS integration = Yes. The Jotform has no logic; its label says "If Yes".
- BellaBot Pre-installation: "Content types" is shown only when the promotional screen is used. "Scheduled shipping date" is a date and "Estimated shipping cost" is a currency; both were numbers in the Jotform.
- BellaBot Installation: the single-choice "Check" (power / Wi-Fi / PUDU Link) became three required ticks. Deployment types were translated to English, because the app is English only.
- Maintenance: the section "B. Pelicano" lists banknote-recycler tasks, so it is named "B. Banknote recycler (NVS200)".
- Jotform PDF manuals are named in section notes. The files themselves still need to be added.
- There is **no automatic machine block** on a "bad" answer such as NO GO or a FAIL. Which answers should block a machine is a product decision; until then the technician uses Block Machine.

## 6. API

`deployops.api.checklists`:
- `start_checklist(job, device)` returns `{doctype, name}`;
- `cancel_checklist(doctype, name, reason)`.

The app's own calls are in [FRONTEND.md](FRONTEND.md).

## 7. Tests

`deployops/tests/test_checklists.py`:
- each card matches its job type and product line;
- refusals: wrong form, a second form, a job that hasn't started, no product line, a Supervisor;
- drafts save with gaps, and submit lists what is missing;
- conditions;
- locking after submit;
- the version stamp and the snapshot saved on submit; an older-version draft cannot be submitted;
- the signature record (signer, time, user, kept until the drawing changes); signer name required;
- evidence files open only for users who can see the form;
- job data is fixed;
- secrets, foreign files and bad signatures are refused;
- **each of the five forms can be completed and submitted**;
- visibility follows the job;
- a Manager can cancel.

`deployops/tests/test_technician_api.py` covers the app API.
