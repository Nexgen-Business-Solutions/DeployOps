import { getPlugin } from "./fields";
import { evaluate } from "./rules";
import type { Answers, ColumnDef, Definition, FieldDef, FormError, RenderMode, TableRow } from "./types";
export function visibleFieldIds(def: Definition, answers: Answers): Set<string> {
	const remaining = { ...answers }, ids = new Set<string>();
	for (const section of def.sections) {
		const shown = evaluate(section.show ?? null, remaining);
		for (const field of section.fields) {
			if (shown && evaluate(field.show ?? null, remaining))
				ids.add(field.id);
			else
				delete remaining[field.id];
		}
	}
	return ids;
}
export function visibleSections(def: Definition, answers: Answers) { const ids = visibleFieldIds(def, answers); return def.sections.map(s => ({ ...s, fields: s.fields.filter(f => ids.has(f.id)) })).filter(s => s.fields.length); }
export function isRequired(field: FieldDef, answers: Answers): boolean { return !!field.required || !!field.required_when && evaluate(field.required_when, answers); }
export function topFieldOf(def: Definition, id: string): string {
	for (const s of def.sections)
		for (const f of s.fields)
			if ((f.config?.columns as ColumnDef[] | undefined)?.some(c => c.id === id))
				return f.id; return id;
}
export function errorsByField(def: Definition, errors: FormError[], answers: Answers) {
	const byField = new Map<string, string>(), general: string[] = [];
	for (const e of errors) {
		const top = e.field ? topFieldOf(def, e.field) : null;
		const field = def.sections.flatMap(s => s.fields).find(f => f.id === top);
		if (!field) {
			general.push(e.message);
			continue;
		}
		let message = e.message;
		if (e.field !== top) {
			const col = ((field.config?.columns ?? []) as ColumnDef[]).find(c => c.id === e.field);
			const rows = (answers[field.id] ?? []) as TableRow[];
			message = `Row ${rows.findIndex(r => r._row === e.row) + 1}: ${col?.label}: ${message}`;
		}
		byField.set(field.id, [byField.get(field.id), message].filter(Boolean).join(" "));
	}
	return { byField, general };
}
export function newRowId(): string { return "r_" + Array.from({ length: 6 }, () => Math.floor(Math.random() * 36).toString(36)).join(""); }
export function fixedRowSeeds(def: Definition, answers: Answers): Answers {
	const out: Answers = {}; for (const s of visibleSections(def, answers))
		for (const f of s.fields) {
			const fixed = f.config?.fixed_rows as {
				column: string;
				labels: string[];
			} | undefined;
			if (f.type === "table" && fixed && !((answers[f.id] as unknown[] | undefined)?.length))
				out[f.id] = fixed.labels.map(label => ({ _row: newRowId(), [fixed.column]: label }));
		} return out;
}
export function displayValue(field: FieldDef, answers: Answers, values: Answers, mode: RenderMode): unknown { return mode === "preview" && field.fill_from && answers[field.id] === undefined ? values[field.fill_from.value] : answers[field.id]; }
export function checkComplete(def: Definition, answers: Answers): FormError[] {
	const errors: FormError[] = [];
	for (const section of visibleSections(def, answers))
		for (const f of section.fields) {
			const plugin = getPlugin(f.type), value = answers[f.id];
			if (!plugin.hasValue)
				continue;
			if (isRequired(f, answers) && plugin.isEmpty(value))
				errors.push({ field: f.id, row: null, message: "This field is required" });
			if (f.type === "checkbox" && f.config?.must_tick && value !== true)
				errors.push({ field: f.id, row: null, message: "This box must be ticked" });
			if (f.type === "table")
				for (const row of (value ?? []) as TableRow[])
					for (const col of (f.config?.columns ?? []) as ColumnDef[])
						if (col.required && getPlugin(col.type).isEmpty(row[col.id]))
							errors.push({ field: col.id, row: row._row, message: "This field is required" });
			if (!plugin.isEmpty(value) || f.type === "table")
				errors.push(...plugin.problems(value, f));
		}
	return errors;
}
export function progress(def: Definition, answers: Answers): number {
	const fields = visibleSections(def, answers).flatMap(s => s.fields).filter(f => getPlugin(f.type).hasValue && (isRequired(f, answers) || f.type === "checkbox" && f.config?.must_tick || f.type === "table" && (Number(f.config?.min_rows) > 0 || f.config?.fixed_rows)));
	const bad = new Set(checkComplete(def, answers).flatMap(e => e.field ? [topFieldOf(def, e.field)] : []));
	return fields.length ? fields.filter(f => !bad.has(f.id)).length / fields.length : 1;
}
export function screenHeader(values: Record<string, unknown>): {
	customer: string | null;
	machine: string | null;
	serial: string | null;
	technician: string | null;
} {
	const text = (v: unknown) => typeof v === "string" ? v : null;
	return { customer: text(values.customer_name), machine: text(values.item_name ?? values.item_code), serial: text(values.serial_no), technician: text(values.technician) };
}
