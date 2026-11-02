"""DeployOps BellaBot Pre-installation checklist (source: https://form.jotform.com/262743846222055; field mapping pending #40 sign-off)."""

from typing import ClassVar

from frappe import _

from deployops.checklists.form import ChecklistForm, is_empty
from deployops.workflow.job_workflow import NO_GO, WITH_CONDITIONS


class DeployOpsBellaBotPreinstallation(ChecklistForm):
	FORM_VERSION = 2  # 2: the "Other" answers of the source form (#24)
	SIGNERS: ClassVar[dict] = {"employee_signature": "technician"}
	ANY_OF: ClassVar[dict] = {
		"content_types_section": ["step_mp4_video", "step_jpeg_image", "step_png_image", "step_gif_image"],
		"operating_days_section": [
			"open_monday",
			"open_tuesday",
			"open_wednesday",
			"open_thursday",
			"open_friday",
			"open_saturday",
			"open_sunday",
		],
	}
	MIN_ROWS: ClassVar[dict] = {"operating_area_photos": 1, "route_photos": 1}
	INTRO = "Pre-installation and site readiness assessment for BellaBot Pro."

	def missing(self) -> list[str]:
		problems = super().missing()
		if self.final_decision in (NO_GO, WITH_CONDITIONS) and is_empty(self.decision_remarks):
			problems.append(_("{0}: required.").format(_(self.meta.get_label("decision_remarks"))))
		return problems
