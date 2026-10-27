# Delivery Note handoff (#16 / #43)

How delivered machines reach installation jobs. DeployOps never changes the Delivery Note; it only reacts when one is submitted or cancelled (`deployops/integrations/delivery_handoff.py`, hooked in `hooks.py`).

## Rules
| Event | What happens |
|---|---|
| Job created from a submitted Delivery Note | Customer, contact and address come from the delivery. Each delivered serial (Serial and Batch Bundle) gets its own machine row, recording its **Delivery Note**, with its own status. |
| A later delivery of the **same sales order** is submitted | Its machines are **added** to the open Installation job that holds the order's earlier delivery, with their own Delivery Note. A comment on the job records it. |
| ... but the job is waiting for review | Nothing is added; a comment says how many machines arrived. |
| ... but the job is completed or cancelled | Nothing happens; a new job can be created from the delivery. |
| ... but the technician is not authorised for a machine | Nothing is added; a comment gives the reason. The delivery itself never fails because of a job. |
| A **return** against the delivery is submitted | Each returned machine on an open job is **flagged** ("Returned on <return>"), but its status doesn't change. A supervisor decides (cancel, block or keep). |
| The return is cancelled | The flag is cleared. |
| The delivery is **cancelled** | Its machines on open jobs are flagged ("Delivery Note <name> was cancelled"). This is a warning only. |

- **Delivery Note** and **Source issue** on a machine row are set by the system only; editing them by hand is refused.
- A job only accepts serials from its own delivery, or from later deliveries of the same order and customer.
- One serial can't be on two open jobs of the same type.

**Owner decisions (2026-10-20), to review with the product owner:** returns are flagged rather than cancelled automatically, and a cancelled or amended delivery is a warning only. Rentals (Subscriptions) are not part of this.

## Tests
`deployops/tests/test_delivery_handoff.py` covers:
- one row per serial, with several serials on one line and several lines;
- a serial not on the delivery is refused;
- a later delivery is added (and only once);
- another order, a job waiting for review and a closed job are left alone;
- a machine the technician isn't authorised for is not added;
- a return flags its machine, and cancelling the return clears the flag;
- a cancelled delivery flags its machines;
- the delivery fields are system-only.
