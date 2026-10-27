"""DeployOps Cashmatic Pre-installation checklist (source: https://form.jotform.com/253063954693264; field mapping pending #40 sign-off)."""

from typing import ClassVar

from deployops.checklists.form import ChecklistForm


class DeployOpsCashmaticPreinstallation(ChecklistForm):
	FORM_VERSION = 1
	SIGNERS: ClassVar[dict] = {"employee_signature": "technician"}
	MIN_ROWS: ClassVar[dict] = {"preparation_photos": 1}
	FIXED_ROWS: ClassVar[dict] = {
		"working_hours": (
			"day",
			("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
		)
	}
	INTRO = "Please complete the following checklist one week before the installation date."
