# DeployOps — Equipment Allocation (#14 / #38)

**Status:** Approved design, implemented on 2026-10-18.
**Code:** [`deployops/equipment/allocations.py`](../deployops/equipment/allocations.py), [`DeployOps Equipment Allocation`](../deployops/deployops/doctype/deployops_equipment_allocation/), [`deployops/api/allocations.py`](../deployops/api/allocations.py), report **Serial Deployment History**.

An **allocation** says which physical machine (ERPNext Serial No) is promised to, or placed with, which customer. ERPNext stays the owner of stock: **DeployOps never creates or edits stock entries** and never writes Serial No. A Subscription only bills; the robot it pays for is recorded here.

---

## 1. Data model

**DeployOps Equipment Allocation** (`DO-ALLOC-.YYYY.-.#####`, change history on)

| Field | Notes |
|---|---|
| Type | **Rental** (source: Subscription) or **Sale** (source: Sales Order) |
| Serial No, Item | The machine; the Item is taken from the serial |
| Company, Source, Customer | Customer comes from the source |
| Status | **Reserved**, **Deployed** (rental placed), **Delivered** (sale handed over by ERPNext), **Returned**, **Swapped Out**, **Cancelled** |
| Reserved On, Deployed / Delivered On, Returned / Closed On, Condition on Return | Timeline |
| Replaces / Replaced By | Links the two allocations of a swap |
| Reserved by Job | For sale reservations made when a machine was picked on a job |
| Movement Log | Every event: when, who, event, job, reference document, note |

**One machine, one active allocation.** Reserved and Deployed are *active*. A hidden `active_serial` field holds the serial while active, and a **unique database index** on it means the database itself refuses a second active allocation, even if two people reserve the same machine at the same moment.

## 2. Rental

| Step | Who | What happens |
|---|---|---|
| **Reserve** | Supervisor, Manager | New allocation from a Subscription. The machine must be **in stock** in ERPNext (status Active, in a warehouse, no customer), not already allocated, within the user's equipment |
| Jobs | — | A job from the Subscription is **pre-filled with its allocated machines**; a rental job may only use machines allocated to that subscription |
| **Deploy** | automatic | When the subscription's **Installation job is approved** (#19), its completed machines become **Deployed** |
| **Return** | Supervisor, Manager | Deployed → **Returned**, with date and a required **condition note**. The machine is free again |
| **Swap** | Supervisor, Manager | Deployed → **Swapped Out** (condition note) and a **new reservation** for the replacement on the same subscription, linked both ways. The replacement is deployed when its installation job is approved |
| **Cancel** | Manager, Admin | Reserved → **Cancelled**, reason required. A deployed machine must be returned instead |

## 3. Sale

| Step | Who | What happens |
|---|---|---|
| **Reserve** | automatic | When a machine (serial) is picked on a job from a **Sales Order**, it is reserved for that order's customer. A machine reserved for one customer cannot be picked for another order, nor rented out |
| **Release** | automatic | Changing the serial on the job, cancelling the machine, or cancelling the job releases the reservation (**Cancelled**, "Released") |
| **Deliver** | automatic | When ERPNext **submits a Delivery Note** with that serial, the reservation becomes **Delivered** (date = posting date). Cancelling the Delivery Note puts it back to **Reserved** |
| Already delivered | — | Picking a serial ERPNext already delivered to the **same** customer needs no reservation; one delivered to **another** customer is refused |

## 4. Who sees which allocation

Same model as jobs (#12): Technician — machines on jobs assigned to them, within their equipment profile; Supervisor / Manager — equipment in their profile; DeployOps Administrator — all. Permissions follow the approved matrix (Technician read; Supervisor create/write; Manager also cancel/export; Admin read/export; nobody deletes).

Status, dates, links and the movement log **can only be changed by the actions above** — not by editing the form, the API or an import.

## 5. Serial Deployment History

Desk → DeployOps → **Serial Deployment History** (also the **Serial History** button on an allocation). For one serial, oldest first:
- **ERPNext** stock moves (receipts, deliveries, returns) from its Serial and Batch Bundles;
- every **allocation** event (reserved, deployed, delivered, returned, swapped, cancelled);
- every **job** the machine was on, with its status.

API: `deployops.api.allocations.serial_history(serial_no)` — needs a DeployOps role and access to that equipment. Allocations and jobs appear only when the caller may read them; stock moves show for anyone with access to the equipment.

## 6. API

`deployops.api.allocations`: `reserve`, `return_machine`, `swap_machine`, `cancel_reservation` (POST), `get_allocation_actions`, `serial_history`, `in_stock_serial_query` (Desk picker: in-stock, unallocated machines of your equipment).

## 7. Tests

`deployops/tests/test_allocations.py` (17 tests): reserve in-stock machine; refusals (not in stock, already allocated, cancelled subscription); who may reserve (Technician no, Supervisor only for their equipment); **database refuses a second active allocation**; rental job pre-filled and approval deploys; return with condition frees the machine; swap; only reservations cancelled, by Manager/Admin; sale reservation on pick; a reserved machine cannot be promised twice nor rented; changing serial or cancelling releases; Delivery Note submit/cancel; already delivered to this customer vs another; status, dates and log cannot be edited directly; visibility per role; serial history content and access.

Also checked on the real DeployOps Demo data (rolled back): a full rental (reserve BBP-0002 → installation approved → Deployed → Returned) and a sale closed by a **real ERPNext Delivery Note** submit, reopened by its cancel.

## 8. UAT steps

1. As sup@test.local (profile New Equipment): **Equipment Allocations → New**, Type Rental, Source ACC-SUB-2026-00001, Serial BBP-0002 → Save. Status Reserved, customer Demo Hotel Bastos.
2. **Jobs → New**: Installation, Source Subscription ACC-SUB-2026-00001 — the machine BBP-0002 appears. Assign tech@test.local and run the workflow to **Approve** (see JOBS.md §7). The allocation shows **Deployed**.
3. On the allocation: **Actions → Return Machine** with a condition. Status Returned; BBP-0002 can be reserved again.
4. Try to reserve a delivered serial (e.g. CM460-0001): refused, not in stock.
5. Open **Serial History** for BBP-0002: stock receipt, reservation, job, deployment, return.
