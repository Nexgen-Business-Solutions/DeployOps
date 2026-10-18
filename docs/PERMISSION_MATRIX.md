# DeployOps — Permission Matrix (#10 / #35)

**Status:** Approved by the owner on 2026-10-18.
**Source of truth in code:** [`deployops/security/matrix.py`](../deployops/security/matrix.py). The tests read that file, so this document and the code must change together.

---

## 1. Roles

The roles ship with the app. They are created automatically on `install-app` and on every `migrate` (`deployops/install.py`, hooked to `before_install` and `before_migrate`). Assign them to any user in **User → Roles**.

| Role (Frappe name) | Alias | Desk (`/desk`) | React (`/`) | Purpose |
|---|---|---|---|---|
| DeployOps Technician | Technician | ❌ | ✅ | Carry out assigned jobs and checklists on authorised equipment |
| DeployOps Supervisor | Supervisor | ✅ | ✅ | Review, reassign and approve within scope |
| DeployOps Manager | Manager | ✅ | ✅ | Oversee the operational domain, scheduling and exceptions |
| DeployOps Administrator | Admin | ✅ | ✅ | Templates, categories, access settings and configuration |

- **Names:** Frappe already has a built-in `Administrator` role, which is why all four roles carry the `DeployOps` prefix. The aliases are used in code (`deployops/roles.py`), in docs and in the React frontend.
- **Technician users are Website Users.** Without Desk access, Frappe makes a Technician-only user a Website User: they can use the React frontend and `/api`, but cannot open Desk.
- **No supplier names.** No role is named after a supplier (Cashmatic, PUDU, BellaBot…). This is tested.

## 2. Role × object matrix

**Key:** R read · C create · W write · S submit · X cancel · D delete · P print · E export · A approve/return · `—` none

| Object | Technician | Supervisor | Manager | Admin |
|---|---|---|---|---|
| DeployOps Job (#18) | R W (assigned) | R C W A P | R C W X A P E | R C W X P E |
| DeployOps Job Device (#16, #18) | R W (assigned) | R C W | R C W X | R C W X |
| DeployOps Checklist Response (#21) | R C W S P (own jobs) | R A P | R X A P E | R P E |
| DeployOps Checklist Template (#20) | R | R | R | R C W |
| DeployOps Equipment Category (#11) | — | R | R | R C W D |
| DeployOps Equipment Access Profile (#11) | — | R | R | R C W D |
| DeployOps Equipment Allocation (#14) | R (own jobs) | R C W | R C W X E | R E |
| DeployOps workspace (Desk) | — | R | R | R |
| React frontend (`/`) | R | R | R | R |

**Rules:**
- **No delete on operational records** (Job, Checklist Response, Allocation). Mistakes are cancelled, so the audit trail stays complete.
- **Admin configures but doesn't approve.** Approval is an operational decision (Supervisor, Manager).
- **Only Manager and Admin can export.**
- **Guests get nothing.** `/` redirects them to `/login`, and no DeployOps API method is open to guests.

**Scope.** This matrix is role-level only. "Assigned" and "own jobs" are enforced later:
- equipment access profiles (#11) limit *which equipment*;
- job assignment (#12) limits *which jobs*.

**"A" (approve/return)** is a workflow transition, enforced in #19, not a DocType permission.

**DocType names** are the candidates from `docs/ARCHITECTURE.md`. When #18 / #20 fix the final names, rename the rows in `matrix.py`. A test fails if any DeployOps DocType is missing from the matrix.

## 3. ERPNext records

DeployOps roles get **no direct permission** on ERPNext records. Data is reached only through DeployOps APIs with their own server-side checks (#13 / #37).

| ERPNext DocType | Technician | Supervisor / Manager / Admin |
|---|---|---|
| Customer, Serial No, Sales Order, Delivery Note, Subscription, Maintenance Visit, Maintenance Schedule | — | — |
| Item | — | list names, print, export, report *(ERPNext default, see below)* |

**Accepted exceptions** (Frappe/ERPNext defaults, not granted by DeployOps):
- **Item:** ERPNext gives the automatic `Desk User` role *select / print / export / report* on Item, and every Desk user has that role. Full read and write stay denied. Technicians have no Desk access and get none of it. Accepted by the owner on 2026-10-18; the tests allow exactly these rights and nothing more.
- **Address and Contact:** Frappe gives the `All` role read/write/create **on records the user created themselves** (`if_owner`). No one can browse other people's addresses or contacts.

## 4. Tests

| Test file | What it proves |
|---|---|
| `deployops/tests/test_matrix_unit.py` (unit, no database) | The matrix is well formed: every row covers all 4 roles with valid letters only; no delete on Job, Checklist Response or Allocation; only Manager and Admin export; Admin never approves; only Technician lacks Desk; the Item exception covers exactly Desk roles and its four rights |
| `deployops/tests/test_permission_matrix.py` | Roles exist with the right Desk access; names are generic; roles can be assigned; Technician users are Website Users; every DeployOps DocType is in the matrix and its permissions match it exactly; ERPNext records are denied except the accepted defaults; the workspace is visible only to Desk roles |
| `deployops/tests/test_security_negative.py` | Over HTTP: guests are redirected from `/` and get 403 on ERPNext APIs; each role gets 403 listing ERPNext records (except the Item default), opening a record by URL (`/api/resource/...`, `frappe.client.get`) and printing it (`/printview`); no DeployOps method is open to guests |
| `deployops/tests/test_install.py` | App installed, ERPNext required, module and workspace set up |

Run them:

```bash
bench --site deployops.local run-tests --app deployops
```

## 5. UAT steps (manual)

1. In Desk, open **User → Roles** and check that the four `DeployOps …` roles are listed.
2. Create a user with only **DeployOps Technician**. Log in as them:
   - `/` opens the React frontend;
   - `/desk` is refused;
   - `/api/resource/Customer` returns 403.
3. Give another user **DeployOps Supervisor**. Log in as them:
   - `/desk` opens, and the **DeployOps** workspace is visible;
   - `/api/resource/Sales Order` returns 403.
4. Log out and open `/`. You are sent to `/login`, and after logging in you return to `/`.
