import { FilesInput } from "./files";
import { SignatureInput } from "./signature";
import type { ComponentType } from "react";
import { ClipboardCheck } from "lucide-react";
import type { Icon } from "../../lib/cards";
import type { ColumnDef, FieldDef, FormError, RenderMode, TableRow } from "../types";
import { BasicInput } from "./basic";
import { ChoiceInput, MultiCheckInput } from "./choice";
import { TableInput } from "./table";
export type { RenderMode } from "../types";
export type RenderContext = {
	mode: RenderMode;
	values: Record<string, unknown>;
	upload?: (file: Blob, filename: string) => Promise<string>;
};
export type FieldInputProps = {
	field: FieldDef | ColumnDef;
	value: unknown;
	disabled: boolean;
	invalid: boolean;
	inputId: string;
	describedBy?: string;
	compact?: boolean;
	ctx: RenderContext;
	onChange: (value: unknown) => void;
};
export type FieldPlugin = {
	type: string;
	label: string;
	icon: Icon;
	hasValue: boolean;
	inTable: boolean;
	labelable: boolean;
	defaultConfig: Record<string, unknown>;
	isEmpty: (value: unknown) => boolean;
	problems: (value: unknown, field: FieldDef) => FormError[];
	Input: ComponentType<FieldInputProps>;
};
const empty = (v: unknown) => v === undefined || v === null || v === "";
function problems(value: unknown, field: FieldDef): FormError[] {
	const c = field.config ?? {}, out: FormError[] = [];
	const error = (message: string) => out.push({ field: field.id, row: null, message });
	if (field.type === "number" && typeof value === "number") {
		if (typeof c.min === "number" && value < c.min)
			error(`Must be at least ${c.min}`);
		else if (typeof c.max === "number" && value > c.max)
			error(`Must be at most ${c.max}`);
	}
	if (field.type === "multi_check") {
		const v = value as {
			selected?: string[];
			other?: string;
		} | null;
		if ((v?.selected?.length ?? 0) + (v?.other ? 1 : 0) < Number(c.min_selected ?? 0))
			error(`Select at least ${c.min_selected}`);
	}
	if (field.type === "table") {
		const rows = (value ?? []) as TableRow[], fixed = c.fixed_rows as {
			column: string;
			labels: string[];
		} | undefined;
		if (rows.length < Number(c.min_rows ?? 0))
			error(`Add at least ${c.min_rows} rows`);
		if (fixed && JSON.stringify(rows.map(r => r[fixed.column])) !== JSON.stringify(fixed.labels))
			error("Rows must match the fixed row labels");
		for (const row of rows)
			for (const col of (c.columns ?? []) as ColumnDef[])
				if (col.id in row)
					out.push(...getPlugin(col.type).problems(row[col.id], { ...col, key: col.id }).map(e => ({ ...e, row: row._row })));
	}
	return out;
}
function fileProblems(value: unknown, field: FieldDef): FormError[] {
	const entries = (value ?? []) as {
		file: string;
	}[], c = field.config ?? {}, out: FormError[] = [];
	const error = (message: string) => out.push({ field: field.id, row: null, message });
	if (typeof c.min === "number" && entries.length < c.min)
		error(`Add at least ${c.min}`);
	if (typeof c.max === "number" && entries.length > c.max)
		error(`Add at most ${c.max}`);
	const allowed = ((c.extensions ?? []) as string[]).map(e => e.toLowerCase().replace(/^\./, ""));
	if (field.type === "files" && allowed.length)
		for (const entry of entries) {
			const basename = entry.file.split("/").at(-1) ?? "";
			const ext = basename.includes(".") ? basename.split(".").at(-1)!.toLowerCase() : "";
			if (!allowed.includes(ext))
				error(`File type .${ext} is not allowed`);
		}
	return out;
}
const tableTypes = new Set(["text", "long_text", "number", "checkbox", "yes_no", "choice", "date", "time"]);
const native = new Set(["text", "long_text", "number", "currency", "date", "time", "datetime", "choice"]);
const labels: Record<string, string> = { text: "Text", long_text: "Long text", number: "Number", currency: "Currency", checkbox: "Checkbox", yes_no: "Yes / No", date: "Date", time: "Time", datetime: "Date and time", info: "Information", choice: "Choice", multi_check: "Multiple choice", table: "Table", photos: "Photos", files: "Files", signature: "Signature" };
export const FIELD_TYPES: FieldPlugin[] = Object.entries(labels).map(([type, label]) => ({
	type, label, icon: ClipboardCheck, hasValue: type !== "info", inTable: tableTypes.has(type), labelable: native.has(type), defaultConfig: type === "choice" || type === "multi_check" ? { options: ["Option 1", "Option 2"] } : type === "table" ? { columns: [{ id: "f_col001", type: "text", label: "Name" }] } : {}, isEmpty: ["table", "photos", "files"].includes(type) ? (v) => !Array.isArray(v) || !v.length : type === "multi_check" ? (v) => {
		const a = v as {
			selected?: unknown[];
			other?: string;
		} | null; return !a || !a.selected?.length && !a.other;
	} : empty, problems: type === "photos" || type === "files" ? fileProblems : problems, Input: type === "signature" ? SignatureInput : type === "photos" || type === "files" ? FilesInput : type === "table" ? TableInput : type === "choice" ? ChoiceInput : type === "multi_check" ? MultiCheckInput : BasicInput
}));
function UnknownInput() { return "This field type is not supported in the app yet."; }
const UNKNOWN_PLUGIN: FieldPlugin = { type: "unknown", label: "Unknown", icon: ClipboardCheck, hasValue: false, inTable: false, labelable: false, defaultConfig: {}, isEmpty: () => true, problems: () => [], Input: UnknownInput };
export function getPlugin(type: string): FieldPlugin { return FIELD_TYPES.find(p => p.type === type) ?? UNKNOWN_PLUGIN; }
