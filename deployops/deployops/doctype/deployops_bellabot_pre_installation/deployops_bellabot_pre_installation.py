"""DeployOps BellaBot Pre-installation checklist (source: https://form.jotform.com/262743846222055; field mapping pending #40 sign-off)."""

from typing import ClassVar

from deployops.checklists.form import ChecklistForm


class DeployOpsBellaBotPreinstallation(ChecklistForm):
	FORM_VERSION = 1
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
