import type { Definition, FieldDef } from "../forms/types";
import type { Op, Condition } from "../forms/rules";
export const operators: [Op, string][] = [["eq", "is"], ["ne", "is not"], ["in", "is one of"], ["not_in", "is not one of"], ["gt", ">"], ["gte", "≥"], ["lt", "<"], ["lte", "≤"], ["empty", "is empty"], ["not_empty", "is filled"], ["contains", "contains"]];
export function earlierFields(def: Definition, id: string): FieldDef[] {
	const fields = def.sections.flatMap(s => s.fields); const index = fields.findIndex(f => f.id === id);
	return fields.slice(0, Math.max(index, 0)).filter(f => f.type !== "info");
}
export function makePredicate(field: string, op: Op, raw: string, type: string): Condition {
	if (op === "empty" || op === "not_empty") return {field, op};
	const parse = (v: string) => type === "number" || type === "currency" ? Number(v) : type === "checkbox" ? v === "true" : v;
	return {field, op, value: op === "in" || op === "not_in" ? raw.split(",").map(v => parse(v.trim())) : parse(raw)};
}
