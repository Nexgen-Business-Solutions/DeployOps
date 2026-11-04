"""DeployOps BellaBot Installation checklist (source: https://form.jotform.com/262743396548066; field mapping pending #40 sign-off)."""

from typing import ClassVar

from frappe import _

from deployops.checklists.form import ChecklistForm


class DeployOpsBellaBotInstallation(ChecklistForm):
	FORM_VERSION = 2  # 2: the "Other" answers of the source form and the required explanations (#25)
	SIGNERS: ClassVar[dict] = {
		"customer_signature": "customer_signatory",
		"technician_signature": "technician",
	}
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
	OTHER_ANSWERS: ClassVar[dict] = {
		"localization_section": "localization_other",
		"safety_section": "safety_other",
		"advertising_section": "advertising_other",
		"audio_section": "audio_other",
		"training_topics_section": "training_topics_other",
		"reminders_section": "reminders_other",
		"advisories_section": "advisories_other",
		"sign_off_section": "sign_off_other",
	}
	REQUIRED_WHEN: ClassVar[dict] = {
		"damage_note": (("visible_damage", "Moderate damage"), ("visible_damage", "Severe damage")),
		"test_notes": (
			("delivery_status", "Fail"),
			("cruise_status", "Fail"),
			("recycle_status", "Fail"),
			("birthday_status", "Fail"),
		),
		"safety_failure_details": (("safety_result", "FAIL"),),
		"customer_remarks": (("handover_confirmed", "No"),),
	}
	MIN_ROWS: ClassVar[dict] = {"arrival_photos": 1, "trainees": 1, "installation_photos": 1}
	INTRO = "BellaBot Pro on-site installation and commissioning (Massarie deployment standard)."

	def block_reason(self) -> str | None:
		reasons = []
		if self.safety_result == "FAIL":
			reasons.append(_("Safety test FAIL: {0}").format(self.safety_failure_details))
		if self.handover_confirmed == "No":
			reasons.append(_("Handover not confirmed: {0}").format(self.customer_remarks))
		return "; ".join(reasons) or None
