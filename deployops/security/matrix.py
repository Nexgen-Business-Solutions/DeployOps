"""Role-level permission matrix (#35). Source of truth for docs/PERMISSION_MATRIX.md and the tests.

Restrictions to specific jobs and equipment are added on top by #11 (equipment access profiles)
and #12 (job assignment). This matrix only says what each role may do at all.

Letters: r read, c create, w write, s submit, x cancel, d delete, p print, e export,
a approve/return. "a" is a workflow transition and is enforced in #19, not by DocPerm.
"""

from deployops.roles import ADMINISTRATOR, DESK_ACCESS, MANAGER, SUPERVISOR, TECHNICIAN

PTYPES = {
	"r": "read",
	"c": "create",
	"w": "write",
	"s": "submit",
	"x": "cancel",
	"d": "delete",
	"p": "print",
	"e": "export",
}

# DocType names are the candidates from docs/ARCHITECTURE.md; rename rows here when #18/#20
# fix the final names. Every DocType in the DeployOps module must have a row (tested).
DOCTYPE_MATRIX = {
	"DeployOps Job": {TECHNICIAN: "rw", SUPERVISOR: "rcwap", MANAGER: "rcwxape", ADMINISTRATOR: "rcwxpe"},
	"DeployOps Job Device": {TECHNICIAN: "rw", SUPERVISOR: "rcw", MANAGER: "rcwx", ADMINISTRATOR: "rcwx"},
	"DeployOps Checklist Response": {
		TECHNICIAN: "rcwsp",
		SUPERVISOR: "rap",
		MANAGER: "rxape",
		ADMINISTRATOR: "rpe",
	},
	"DeployOps Checklist Template": {TECHNICIAN: "r", SUPERVISOR: "r", MANAGER: "r", ADMINISTRATOR: "rcw"},
	"DeployOps Equipment Category": {TECHNICIAN: "", SUPERVISOR: "r", MANAGER: "r", ADMINISTRATOR: "rcwd"},
	"DeployOps Equipment Access Profile": {
		TECHNICIAN: "",
		SUPERVISOR: "r",
		MANAGER: "r",
		ADMINISTRATOR: "rcwd",
	},
	"DeployOps Equipment Allocation": {
		TECHNICIAN: "r",
		SUPERVISOR: "rcw",
		MANAGER: "rcwxe",
		ADMINISTRATOR: "re",
	},
}

# ERPNext records are reached only through DeployOps APIs with their own checks (#13 / #37).
# DeployOps roles get no direct permission on them.
ERPNEXT_DENIED = (
	"Customer",
	"Item",
	"Serial No",
	"Sales Order",
	"Delivery Note",
	"Subscription",
	"Maintenance Visit",
	"Maintenance Schedule",
)

# Known exception, accepted by the owner: ERPNext grants Frappe's automatic "Desk User" role
# select/print/export/report on Item, so every Desk user gets it (Supervisor, Manager, Admin).
# Technicians have no Desk access and get none of it. These are the only rights allowed.
DESK_USER_ERPNEXT_DEFAULTS = {"Item": ("select", "print", "export", "report")}

DESK_ROLES = tuple(role for role, desk_access in DESK_ACCESS.items() if desk_access)

WORKSPACE_ROLES = DESK_ROLES

# Role names must stay generic.
SUPPLIER_NAMES = ("cashmatic", "pudu", "bellabot")


def allowed(doctype: str, role: str, ptype: str) -> bool:
	"""Return True if the matrix grants `ptype` (e.g. "read") on `doctype` to `role`."""
	letters = DOCTYPE_MATRIX[doctype][role]
	return any(PTYPES.get(letter) == ptype for letter in letters)


def erpnext_allowed(doctype: str, role: str, ptype: str) -> bool:
	"""Return True only for the accepted ERPNext Desk User defaults; everything else is denied."""
	return role in DESK_ROLES and ptype in DESK_USER_ERPNEXT_DEFAULTS.get(doctype, ())
