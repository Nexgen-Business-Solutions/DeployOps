"""DeployOps BellaBot Installation checklist (source: https://form.jotform.com/262743396548066; field mapping pending #40 sign-off)."""

from typing import ClassVar

from deployops.checklists.form import ChecklistForm


class DeployOpsBellaBotInstallation(ChecklistForm):
	FORM_VERSION = 1
	ANY_OF: ClassVar[dict] = {
		"localization_section": [
			"step_initial_localization",
			"step_re_localization_confirmed",
			"step_tag_marker_alignment_checked",
		],
		"modes_section": [
			"step_delivery",
			"step_cruise",
			"step_recycle",
			"step_birthday",
			"step_guide_escorting",
			"step_shop_assistant",
			"step_advertising",
		],
		"safety_section": [
			"step_obstacle_detection",
			"step_emergency_stop",
			"step_human_interaction_safety",
			"step_low_speed_stop_behavior",
			"step_audible_visual_warning_response",
		],
		"advertising_section": ["step_video_display", "step_image_slideshow", "step_promotional_banners"],
		"audio_section": [
			"step_greeting_announcements",
			"step_promotional_announcements",
			"step_alert_tones",
		],
		"training_topics_section": [
			"step_basic_operation",
			"step_charging",
			"step_safety_procedures",
			"step_cleaning_and_maintenance",
			"step_touch_screen_interface_usage",
			"step_route_delivery_management",
			"step_emergency_stop_and_recovery",
			"step_pudu_link_app_installed_and_configured_on",
			"step_call_function_pager_via_the_pudu_link_app",
			"step_touch_sensors_and_voice_interaction",
		],
		"reminders_section": [
			"step_keep_the_robot_and_charging_contacts_clean",
			"step_inspect_wheels_brushes_and_sensors",
		],
		"advisories_section": [
			"step_daily_cleaning_guidance",
			"step_weekly_inspection_checklist",
			"step_battery_care_guidance",
			"step_safe_operating_area_guidance",
			"step_service_contact_information",
		],
		"sign_off_section": [
			"step_i_confirm_the_installation_and",
			"step_i_confirm_any_outstanding_issues_have_been",
			"step_i_confirm_the_site_is_ready_for_handover",
		],
	}
	MIN_ROWS: ClassVar[dict] = {"arrival_photos": 1, "trainees": 1, "installation_photos": 1}
	INTRO = "BellaBot Pro on-site installation and commissioning (Massarie deployment standard)."
