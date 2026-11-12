import type { Rule } from "./rules";
export type FieldDef = {
	id: string;
	key: string;
	type: string;
	label: string;
	help?: string;
	required?: boolean;
	show?: Rule | null;
	required_when?: Rule | null;
	fill_from?: {
		value: string;
		locked?: boolean;
	};
	outcomes?: {
		when: Rule;
		effect: string;
	}[];
	config?: Record<string, unknown>;
};
export type ColumnDef = {
	id: string;
	type: string;
	label: string;
	required?: boolean;
	config?: Record<string, unknown>;
};
export type SectionDef = {
	id: string;
	title?: string;
	description?: string;
	show?: Rule | null;
	fields: FieldDef[];
};
export type Definition = {
	schema: number;
	sections: SectionDef[];
	references?: {
		file: string;
		title: string;
		show_in: string[];
		hash?: string;
	}[];
};
export type Answers = Record<string, unknown>;
export type TableRow = {
	_row: string;
} & Record<string, unknown>;
export type FormError = {
	field: string | null;
	row: string | null;
	message: string;
};
export type ScreenReference = {
	title: string;
	url: string;
	show_in: string[];
};
export type SubmissionView = {
	name: string;
	docstatus: 0 | 1 | 2;
	form: string;
	form_version: string;
	version_no: number;
	title: string;
	context_doctype: string | null;
	context_name: string | null;
	context_row: string | null;
	amended_from: string | null;
	answers: Answers;
	definition: Definition;
	context_values: Record<string, unknown>;
	can_write: boolean;
	can_submit: boolean;
	submitted_by: string | null;
	submitted_on: string | null;
	references: ScreenReference[];
};
export type RenderMode = "fill" | "readonly" | "preview";
export type MachineFormEntry = {
	form: string;
	title: string;
	subtitle: string | null;
	icon: string | null;
	color: string | null;
	required: boolean;
	origin: string;
	status: "Not started" | "Draft" | "Submitted";
	submission: string | null;
	form_version: string | null;
	flagged: boolean;
	can_start: boolean;
	can_remove: boolean;
	remove_needs_manager: boolean;
	can_discard: boolean;
	can_cancel: boolean;
};
export type MachineFormsView = {
	job: string;
	row: string;
	item_code: string;
	serial_no: string | null;
	device_status: string;
	job_status: string;
	frozen: boolean;
	uses_forms: boolean;
	forms: MachineFormEntry[];
	can_add: boolean;
	addable: {
		form: string;
		title: string;
	}[];
};
export type FormCard = {
	form: string;
	title: string;
	subtitle: string | null;
	icon: string | null;
	color: string | null;
	job_types: string[];
	open_jobs: number;
	attention: number;
	waiting: boolean;
	outstanding: number;
	flagged: number;
};
export type FormJobRow = {
	name: string;
	job_type: string;
	customer_name: string;
	address_display: string | null;
	planned_date: string | null;
	status: string;
	machines: number;
	outstanding: number;
	flagged: number;
};
