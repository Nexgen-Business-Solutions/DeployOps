# DeployOps Frontend (Technician app)

The React app at `/deployops` is where technicians do field work: pick a checklist, open a job, work on each machine and fill in its checklist. Supervisor and Manager screens come later. Until then they use Desk.

## Agreed design
| Decision | Choice |
|---|---|
| Language | English only |
| Home | Five fixed checklists, defined in `deployops/checklists/cards.py` |
| Stack | React 19, TypeScript, Tailwind 4, React Router 7, a small `fetch` wrapper (`frontend/src/lib/api.ts`), lucide icons, Inter font |
| Connectivity | Online only. Unsaved answers stay queued while offline and are sent when the connection returns, as long as the page stays open. |
| Look | "Clean mono": white background, near-black text, thin dividers, list rows instead of boxes. Blue `#2b7fff` (Tailwind blue-500) appears only on actions, selections and progress. Mobile first. |
| Login | The app's own sign-in screen, not the Frappe `/login` page |
| Forms | One long page split into numbered sections, with a progress bar under the top bar and a sticky Submit button |

## Screens
All routes are under `/deployops` (the router's base); DeployOps leaves every other URL to Frappe and the other apps.

| Route | Screen |
|---|---|
| `/deployops` | Sign in for guests; otherwise Home: greeting, open job count, the five checklists with counts |
| `/deployops/c/{card}` | My open jobs for that checklist |
| `/deployops/job/{name}` | Job: planned date, site (maps link), contact (call link), source, job actions; machines with Start / Continue checklist and machine actions |
| `/deployops/form/{doctype}/{name}` | The checklist form; read only once submitted |

## Cards
| Card | Job type | Product line | DocType |
|---|---|---|---|
| Cashmatic Pre-installation | Pre-installation | Cashmatic | DeployOps Cashmatic Pre-installation |
| Cashmatic Installation | Installation | Cashmatic | DeployOps Cashmatic Installation |
| BellaBot Pre-installation | Pre-installation | BellaBot | DeployOps BellaBot Pre-installation |
| BellaBot Installation | Installation | BellaBot | DeployOps BellaBot Installation |
| Cashmatic Maintenance | Maintenance | Cashmatic | DeployOps Cashmatic Maintenance |

A card lists my open jobs of its job type that have a machine in its product line. The product line is set on the machine's equipment category (field **Checklist product line**).

## API (`deployops/api/technician.py`)
| Method | Use |
|---|---|
| `me` | Current user, role aliases, Desk access. Refused for guests and for users without a DeployOps role. |
| `home` | The five cards with my open job counts |
| `my_jobs(card)` | Open jobs for a card |
| `job_view(job)` | Job details, the actions allowed now, machines with their form (`{doctype, name, submitted}`) |
| `form_view(doctype, name)` | Header, sections and fields read from the DocType itself, current values, whether I can edit |
| `save_form(doctype, name, values)` | Partial save (POST), used by autosave |
| `submit_form(doctype, name)` | Submit (POST) |

The app also uses these existing methods:
- `deployops.api.jobs.job_action`
- `deployops.api.jobs.device_action`
- `deployops.api.checklists.start_checklist`

Photos and files go through Frappe's `upload_file` as **private** files attached to the form.

## How a DocType becomes a screen
The app renders whatever the DocType defines, so changing a field in the DocType changes the screen.

| Frappe field type | In the app |
|---|---|
| Section Break | Numbered heading. "Tick at least one" when the form declares it in `ANY_OF`. |
| Check | Tappable step row with a round tick. Consecutive steps form one list. |
| Select | Two or three short options: pills. Up to 8: radio rows. More: dropdown. |
| Data, Small Text, Text | Input or text area |
| Int, Float, Currency | Number input |
| Date, Datetime, Time | Native pickers |
| Signature | Finger or mouse pad, stored as a PNG |
| Table → Photo / File | Thumbnail grid or file list with upload, drag and drop, and a count against the minimum |
| Table with fixed rows | Row per day or task (times / closed, Yes / No / remarks) |
| Other Table | Repeating cards with Add and remove |
| HTML | Grey note |

**Reference documents (#42).** The manuals an administrator lists in **DeployOps Reference Files** show up in two places:
- a **"Documents for this checklist"** block at the top of the form, listing each document once with the sections that use it;
- a card under each section that needs one.

Each card has a first-page preview and the page count. **Read** opens a full-screen, page-by-page viewer, with a download button and arrow keys and Escape on a keyboard. Images open as they are.

Rendering uses **pdf.js** (`pdfjs-dist`, its *legacy* build, because the modern build needs JavaScript that today's phones lack). It's loaded only when a checklist has documents, and the worker is a separate file of about 1.3 MB. The files stay private: only DeployOps users can open them.

`depends_on` / `mandatory_depends_on` (`eval:doc.<field>=='<value>'`) show and require fields live. The app checks the same rules as the server before submit (`frontend/src/lib/form.ts`), marks problems in place and scrolls to the first one.

## Security
- The server decides everything: visibility, actions, editing and validation. The UI only hides buttons the server would refuse anyway.
- `www/deployops.py` serves guests an empty shell with no data; every technician API refuses guests.
- Uploaded files must be private and attached to the same form. File access follows the form's permission, so it follows job visibility.
- Text that looks like a password, PIN, OTP or pairing code is refused.
- Nothing is stored in local storage.

## Development
```bash
cd apps/deployops/frontend
yarn dev          # http://<site>:8080/deployops, proxies /api to bench
yarn typecheck && yarn lint && yarn test
yarn build        # writes deployops/public/frontend and www/deployops.html
bench --site deployops.local clear-cache
```
