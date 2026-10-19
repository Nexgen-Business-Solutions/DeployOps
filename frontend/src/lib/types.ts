// Shapes returned by deployops.api.technician (see deployops/api/technician.py).

export type Me = {
	user: string;
	full_name: string;
	roles: string[];
	has_desk: boolean;
};

export type Card = {
	id: string;
	title: string;
	subtitle: string;
	job_type: string;
	product_line: string;
	doctype: string;
	icon: string;
	open_jobs: number;
	waiting: boolean;
};

export type JobRow = {
	name: string;
	customer_name: string;
	address_display: string | null;
	planned_date: string | null;
	status: string;
	machines: number;
};

export type Action = { action: string; label: string; reason_required: boolean };

export type FormRef = { doctype: string; name: string; submitted: boolean };

export type Machine = {
	row: string;
	item_code: string;
	item_name: string | null;
	serial_no: string | null;
	status: string;
	actions: Action[];
	checklist: FormRef | null;
	can_start_checklist: boolean;
};

export type JobView = {
	name: string;
	job_type: string;
	status: string;
	customer_name: string;
	address: string | null;
	contact: string | null;
	planned_date: string | null;
	source: string;
	actions: Action[];
	machines: Machine[];
};

export type Condition = { field: string; value: string } | null;

export type Column = {
	fieldname: string;
	fieldtype: string;
	label: string;
	options: string[];
	reqd: boolean;
	read_only: boolean;
};

export type TableInfo = {
	kind: "photos" | "files" | "grid" | "rows";
	columns: Column[];
	file_column: string | null;
	min_rows: number;
};

export type Field = {
	fieldname: string;
	fieldtype: string;
	label: string;
	description: string | null;
	reqd: boolean;
	read_only?: boolean;
	show: Condition;
	options?: string[];
	text?: string;
	table?: TableInfo;
};

export type Section = {
	name: string;
	label: string;
	description: string | null;
	any_of: boolean;
	show?: Condition;
	fields: Field[];
};

export type Row = Record<string, string | number | null> & { name?: string };
export type Value = string | number | null | Row[];
export type Values = Record<string, Value>;

export type FormView = {
	doctype: string;
	name: string;
	title: string;
	intro: string;
	form_version: number | null;
	job: string;
	header: Record<string, string | null>;
	technician_name: string | null;
	docstatus: number;
	submitted_by: string | null;
	submitted_on: string | null;
	can_edit: boolean;
	sections: Section[];
	values: Values;
	signatures: Record<string, { signer_name: string | null; signed_on: string | null }>;
};
