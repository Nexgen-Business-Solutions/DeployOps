# Cashmatic pre-installation: setup to completion

For a fresh ERPNext + DeployOps installation. This guide covers a **sold Cashmatic machine**, ending at approved pre-installation.

## Set up once

1. **Complete ERPNext setup.** Configure Company, currency, accounts, fiscal year, warehouse and a selling Price List.
2. **Enable serial tracking.** In Stock Settings, enable **Activate Serial / Batch No for Item**.
3. **Create the machine Item.** Example: `CM-460`, Cashmatic SelfPay 460. Enable **Maintain Stock** and **Has Serial No**; use a unit such as Nos. One Item represents the model; Serial Nos identify individual machines.
4. **Receive the machine into stock.** Use a submitted **Purchase Receipt** for a supplier purchase, or **Stock Entry → Material Receipt** for opening/demo stock. Enter the warehouse, quantity, valuation/purchase rate and actual serial numbers through ERPNext's serial/bundle fields. Do not create a second machine master.
5. **Set the selling price.** Create an **Item Price** for the Item, selling Price List and currency. Alternatively, enter an agreed rate directly on the Sales Order.
6. **Register staff in User.** Create or reuse enabled users. Assign **DeployOps Technician**, **DeployOps Supervisor**, **DeployOps Manager** and **DeployOps Administrator** according to responsibilities. Technician-only users use the technician app; supervisors/managers use Desk for planning and review. An Employee record is not required for job assignment.
7. **Give office staff ERPNext access.** Assign suitable ERPNext sales/stock permissions to the staff handling Items, receipts, customers and orders. DeployOps roles alone do not grant these rights.
8. **Configure equipment access.** As DeployOps Administrator, create an enabled **DeployOps Equipment Category**, set **Checklist product line = Cashmatic**, and add the machine Item. Avoid overlapping categories that give the same Item different product lines.
9. **Authorize the team.** Create an enabled **DeployOps Equipment Access Profile** for each Technician, Supervisor and Manager; add that category. Preserve any other categories they need.

## Prepare each customer job

10. **Create the customer and site.** Create Customer, linked Contact and shipping Address. Select the correct contact/site on the order before creating the job.
11. **Confirm the sale.** Create and **submit a Sales Order** with the machine Item, quantity, rate and delivery date. A Draft, On Hold or Closed order cannot start this flow. Each unit ordered becomes a device row.
12. **Create the preparation job.** In Desk, open **DeployOps Job → New**. Set Company, **Job Type = Pre-installation**, **Source Type = Sales Order**, and select the submitted order. Review the filled customer/site and device rows.
13. **Assign and schedule.** Set **Assigned Technician** and **Planned Date**. Select an available matching **Serial No** on each device row and save. Selecting a serial reserves it for the sale. The serial can also be picked later during preparation (the technician screen has no serial picker, so use Desk): a draft checklist follows the job's serial, and a checklist **cannot be submitted until the machine has a serial**. Once submitted, its serial is frozen.
14. **Start preparation.** As Supervisor or Manager, choose **Actions → Start**. The job becomes **In Preparation**. Plan preparation about one week before installation, as the checklist instructs.

## Technician checks and supervisor approval

15. **Open the assigned work.** Technician signs in at **`/deployops`**, selects **Cashmatic Pre-installation**, opens the job and confirms customer, site, Item and serial.
16. **Perform the checklist.** Choose **Start Machine**, then **Start checklist**. Follow the displayed documentation, customer readiness, configuration, activation and packing/accessory steps. Record software/firmware versions, activation date, working hours and special installation notes. Upload at least one preparation photo; complete required answers and capture the employee signature when applicable. Never record credentials or pairing codes.
17. **Submit the work.** Choose **Submit checklist** and resolve any highlighted missing answers. Return to the job, choose **Complete Machine** for each finished device (refused until its checklist is submitted), then **Submit for Review**. If something prevents preparation, use **Block Machine** or **Block** with a reason; the supervisor resolves and unblocks it.
18. **Review and approve.** Supervisor or Manager checks the submitted checklist and evidence, then chooses **Approve**. The job becomes **Completed**. **Return for Correction** requires a reason; submitted checklists remain locked, so answer changes require the Manager's checklist cancellation/replacement process.

**If the technician cannot find the job:** check the enabled user and role, equipment category/product line, enabled access profile, assigned technician and job state. A job must be **In Preparation** before its checklist can start.

**End point:** approved preparation with a serial-linked checklist. Delivery Note and on-site installation are later, separate steps. Checklist submission, machine completion and job approval are separate actions, in that order.

**Acceptance:** the hand-run scenarios are in [CASHMATIC_PREINSTALLATION_UAT.md](CASHMATIC_PREINSTALLATION_UAT.md); the field mapping against the original Jotform, with the open decisions, is in [CASHMATIC_PREINSTALLATION_MAPPING.md](CASHMATIC_PREINSTALLATION_MAPPING.md).
