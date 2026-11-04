"""DeployOps BellaBot Pre-installation checklist (source: https://form.jotform.com/262743846222055; field mapping pending #40 sign-off)."""

from typing import ClassVar

from deployops.checklists.form import ChecklistForm
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
	REQUIRED_WHEN: ClassVar[dict] = {
		"decision_remarks": (("final_decision", NO_GO), ("final_decision", WITH_CONDITIONS)),
	}
	NUMBER_RANGES: ClassVar[dict] = {  # the source form's own limits
		"narrowest_passage_cm": (0, 500),
		"kitchen_entrance_cm": (0, 500),
		"max_dish_size_cm": (0, 500),
		"two_way_corridor_cm": (0, 500),
		"slope_degrees": (0, 90),
	}
	MIN_ROWS: ClassVar[dict] = {"operating_area_photos": 1, "route_photos": 1}
	INTRO = "Pre-installation and site readiness assessment for BellaBot Pro."

	def block_reason(self) -> str | None:
		return f"{NO_GO}: {self.decision_remarks}" if self.final_decision == NO_GO else None
