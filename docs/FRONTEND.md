# DeployOps Frontend (Technician app)

The React app at `/` is where technicians do field work: pick a checklist, open a job, work on each machine and fill in its checklist. Supervisor and Manager screens come later. Until then they use Desk.

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
| Route | Screen |
|---|---|
| `/` | Sign in for guests; otherwise Home: greeting, open job count, the five checklists with counts |
| `/c/{card}` | My open jobs for that checklist |
| `/job/{name}` | Job: planned date, site (maps link), contact (call link), source, job actions; machines with Start / Continue checklist and machine actions |
| `/form/{doctype}/{name}` | The checklist form; read only once submitted |

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

`depends_on` / `mandatory_depends_on` (`eval:doc.<field>=='<value>'`) show and require fields live. The app checks the same rules as the server before submit (`frontend/src/lib/form.ts`), marks problems in place and scrolls to the first one.

## Security
- The server decides everything: visibility, actions, editing and validation. The UI only hides buttons the server would refuse anyway.
- `www/frontend.py` serves guests an empty shell with no data; every technician API refuses guests.
- Uploaded files must be private and attached to the same form. File access follows the form's permission, so it follows job visibility.
- Text that looks like a password, PIN, OTP or pairing code is refused.
- Nothing is stored in local storage.

## Development
```bash
cd apps/deployops/frontend
yarn dev          # :8080, proxies /api to bench
yarn typecheck && yarn lint && yarn test
yarn build        # writes deployops/public/frontend and www/frontend.html
bench --site deployops.local clear-cache
```
