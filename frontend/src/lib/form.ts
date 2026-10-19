// Form rules the app shows while typing. The server re-checks all of them on save and submit
// (deployops/checklists/form.py); keep the two in step.

import type { Condition, Field, Row, Section, Value, Values } from "./types";

const NO_VALUE = new Set(["HTML", "Section Break", "Column Break"]);

export function conditionMet(condition: Condition | undefined, values: Values): boolean {
	if (!condition) return true;
	return (values[condition.field] ?? "") === condition.value;
}

export function isEmpty(value: Value | undefined): boolean {
	if (value === null || value === undefined) return true;
	if (typeof value === "string") return !value.trim();
	if (Array.isArray(value)) return value.length === 0;
	return false;
}

/** Fields that need an answer: everything required, except HTML notes and "at least one" boxes. */
function counts(section: Section, field: Field): boolean {
	return field.reqd && !NO_VALUE.has(field.fieldtype) && !(section.any_of && field.fieldtype === "Check");
}

function rowProblem(field: Field, row: Row): string | null {
	const table = field.table;
	if (!table) return null;
	if (table.columns.some((c) => c.fieldname === "closed")) {
		return row.closed || (row.open_time && row.close_time) ? null : "Add times or mark closed.";
	}
	const missing = table.columns.find((c) => c.reqd && !c.read_only && isEmpty(row[c.fieldname]));
	return missing ? `${missing.label} is required.` : null;
}

function fieldProblem(section: Section, field: Field, values: Values): string | null {
	const value = values[field.fieldname];
	if (field.fieldtype === "Table" && field.table) {
		const rows = (value as Row[] | null) ?? [];
		const minimum = field.table.min_rows;
		if (rows.length < minimum) return minimum > 1 ? `Add at least ${minimum}.` : "Required.";
		for (const row of rows) {
			const problem = rowProblem(field, row);
			if (problem) return problem;
		}
		return null;
	}
	if (!counts(section, field)) return null;
	if (field.fieldtype === "Check") return value ? null : "Tick to confirm.";
	return isEmpty(value) ? "Required." : null;
}

export function visibleSections(sections: Section[], values: Values): Section[] {
	return sections
		.filter((section) => conditionMet(section.show, values))
		.map((section) => ({ ...section, fields: section.fields.filter((f) => conditionMet(f.show, values)) }))
		.filter((section) => section.fields.length);
}

/** Problems keyed by field name, or by section name for "tick at least one". */
export function findProblems(sections: Section[], values: Values): Map<string, string> {
	const problems = new Map<string, string>();
	for (const section of visibleSections(sections, values)) {
		const boxes = section.fields.filter((f) => f.fieldtype === "Check");
		if (section.any_of && boxes.length && !boxes.some((f) => values[f.fieldname])) {
			problems.set(section.name, "Tick at least one.");
		}
		for (const field of section.fields) {
			const problem = fieldProblem(section, field, values);
			if (problem) problems.set(field.fieldname, problem);
		}
	}
	return problems;
}

/** Share of required answers given, for the progress bar (0–1). */
export function progress(sections: Section[], values: Values): number {
	let total = 0;
	let done = 0;
	for (const section of visibleSections(sections, values)) {
		if (section.any_of) {
			total += 1;
			if (section.fields.some((f) => f.fieldtype === "Check" && values[f.fieldname])) done += 1;
		}
		for (const field of section.fields) {
			const table = field.fieldtype === "Table" && field.table && field.table.min_rows > 0;
			if (!table && !counts(section, field)) continue;
			total += 1;
			if (!fieldProblem(section, field, values)) done += 1;
		}
	}
	return total ? done / total : 1;
}

export function toInputDatetime(value: Value | undefined): string {
	return typeof value === "string" && value ? value.replace(" ", "T").slice(0, 16) : "";
}

export function fromInputDatetime(value: string): string | null {
	return value ? `${value.replace("T", " ")}:00` : null;
}

export function toInputTime(value: Value | undefined): string {
	if (typeof value !== "string" || !value) return "";
	const [h = "0", m = "00"] = value.split(":");
	return `${h.padStart(2, "0")}:${m}`;
}

export function formPath(doctype: string, name: string): string {
	return `/form/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`;
}
