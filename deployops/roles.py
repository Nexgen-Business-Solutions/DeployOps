"""DeployOps roles.

The full names are the Role IDs Frappe stores and shows in Desk. The aliases are the short
labels used in code, documentation and the React frontend.
"""

TECHNICIAN = "DeployOps Technician"
SUPERVISOR = "DeployOps Supervisor"
MANAGER = "DeployOps Manager"
ADMINISTRATOR = "DeployOps Administrator"

ALIASES = {
	TECHNICIAN: "Technician",
	SUPERVISOR: "Supervisor",
	MANAGER: "Manager",
	ADMINISTRATOR: "Admin",
}

ALL_ROLES = tuple(ALIASES)

# Technicians use the React frontend only; the other roles may also open Desk.
DESK_ACCESS = {
	TECHNICIAN: 0,
	SUPERVISOR: 1,
	MANAGER: 1,
	ADMINISTRATOR: 1,
}
