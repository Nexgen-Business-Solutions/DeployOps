# DeployOps — ERPNext Source Lookups (#13 / #37)

**Status:** Approved rules, implemented on 2026-10-18.
**Code:** [`deployops/integrations/erpnext_sources.py`](../deployops/integrations/erpnext_sources.py) (validation and snapshots) and [`deployops/api/sources.py`](../deployops/api/sources.py) (whitelisted API).

DeployOps **reads** ERPNext records and never writes them. DeployOps roles have no direct ERPNext permissions ([PERMISSION_MATRIX.md](PERMISSION_MATRIX.md) §3), so these lookups are the only way DeployOps users reach source data, and they apply DeployOps' own checks.

---

## 1. Usable sources

| Source | Usable when | Refused when |
|---|---|---|
| Sales Order | submitted | draft, cancelled, **Closed**, **On Hold** |
| Delivery Note | submitted | draft, cancelled, **return** |
| Subscription | customer subscription | **Cancelled**, **Completed**, or not for a Customer |
| Maintenance Visit | **draft or submitted** (the checklist is done during the visit) | cancelled |
| Maintenance Schedule | submitted | draft, cancelled |

- **Company:** when a company is given (the job's company), the source must belong to it.
- **Payment gating** (whether a Sales Order must be paid or invoiced first) is decided in #15, not here.

## 2. What a lookup returns (snapshot)

`customer`, `customer_name`, `company`, `status`, `docstatus`, plus:
- **contact:** the source's `contact_person`, or else the Customer's primary contact. Fields: name, full name, email, phone, mobile.
- **address:** the source's shipping or customer address, or else the Customer's primary address. Name and formatted text.
- **lines:** one per item row, with `item_code`, `item_name`, `qty` and `serial_nos`. Several machines on one Delivery Note stay separate lines.
- **plans:** Subscription plans only.

**Serial numbers on a row** come from the row's **Serial and Batch Bundle** (ERPNext v16). If there is no bundle, or it is cancelled, they come from the older `serial_no` text field.

**Subscriptions never yield a device.** A Subscription bills service plans. The physical device is allocated separately (#14), so DeployOps never guesses a serial from a plan.

## 3. API (`deployops.api.sources`)

| Method | Purpose |
|---|---|
| `get_source_summary(doctype, name, company=None)` | Validate a source and return its snapshot |
| `search_sources(doctype, txt="", company=None, limit=20)` | Usable sources matching a name or customer (at most 50) |
| `get_serial(serial_no, item_code=None, company=None)` | Check that a Serial No exists, matches the Item and company, and return its key fields |

**Access rules:**
- **Who:** any user with a DeployOps role. Guests and users without a DeployOps role are refused (403).
- **Which equipment:** lines are limited to the equipment in the caller's **access profile** (#36). A source with none of the caller's equipment is refused. DeployOps Administrators are unrestricted.
- **Subscriptions** are not refused for lack of equipment, because they carry none.

## 4. Tests

| Test file | What it proves |
|---|---|
| `deployops/tests/test_erpnext_sources.py` | Every source type in valid and invalid states; company boundary; unknown type and missing record; snapshot customer, contact, address and lines; fallback to the Customer's primary contact and address; serials from the bundle, from the text field, and from the text field when the bundle is cancelled; several machines on one Delivery Note; a Subscription never yields a device; serial checks (item, company, missing); the API needs a DeployOps role, filters lines by profile, refuses sources with none of the user's equipment, restricts Supervisors too, gives Admin every line, allows Subscriptions; search returns only usable and authorised sources; `get_serial` respects equipment |
| `deployops/tests/test_security_negative.py` | Guests get 403 on all three API methods over HTTP |

The tests write ERPNext documents straight to the database in the exact state under test (`tests/erpnext_fixtures.py`). DeployOps only reads them, so the tests don't depend on the site's accounting or stock setup and run on a fresh CI site.

## 5. Known limits
- `search_sources` checks up to 5 × `limit` recent candidates. If most of them are unusable or outside the caller's equipment, it can return fewer than `limit` results.
- Nothing is stored yet. Jobs (#18) will keep the source link and a snapshot.
