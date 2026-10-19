"""DeployOps Cashmatic Installation checklist (source: https://form.jotform.com/253064644317254; field mapping pending #40 sign-off)."""

from typing import ClassVar

from deployops.checklists.form import ChecklistForm


class DeployOpsCashmaticInstallation(ChecklistForm):
	FORM_VERSION = 1
	ANY_OF: ClassVar[dict] = {
		"web_panel_explanation_section": [
			"step_level_status",
			"step_standard_operations",
			"step_extraordinary_operations",
			"step_reports",
			"step_settings",
			"step_logs",
			"step_users_management",
			"step_update",
			"step_info",
			"step_door_access",
			"step_shutdown_restart",
			"step_change_language",
		],
		"firsthand_training_section": [
			"step_make_a_payment",
			"step_refill_deposit",
			"step_withdraw_and_withdraw_by_denomination",
			"step_monitor_transactions_by_day_in_reports",
			"step_edit_users",
			"step_change_device_settings",
			"step_open_the_door",
			"step_empty_and_float_all_options",
			"step_download_the_log_to_identify_a_problem",
			"step_tip_management",
			"step_remove_the_cashbox_auto_and_manual_reset",
			"step_remove_the_recycler_and_check_info",
			"step_remove_the_smart_hopper_and_check_info",
		],
		"problem_solving_section": [
			"step_error_codes_and_simple_recovery",
			"step_jammed_notes_and_how_to_solve_them",
			"step_jammed_coins_and_how_to_solve_them",
		],
		"warnings_section": [
			"step_review_the_warnings_for_use",
			"step_review_the_precautions_for_use",
			"step_review_the_maintenance_instructions",
			"step_disposal_precautions_when_purchased",
		],
	}
	MIN_ROWS: ClassVar[dict] = {"installation_photos": 3}
	INTRO = "Please complete the following checklist before leaving the site."
