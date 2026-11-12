import type { Definition, FieldDef, SectionDef, ColumnDef } from "../forms/types";
import { replaceReference } from "./safety";
import { newId } from "./ids";
export type BuilderDefinition = Definition & {title?: string; appearance?: Record<string, string>};
export type Action =
	| {type: "addSection"; section: SectionDef}
	| {type: "moveSection"; id: string; index: number}
	| {type: "deleteSection" | "deleteField"; id: string}
	| {type: "duplicateSection" | "duplicateField"; id: string; ids?: Record<string, string>}
	| {type: "addField"; section: string; field: FieldDef; index?: number}
	| {type: "moveField"; id: string; section: string; index: number}
	| {type: "updateField"; id: string; patch: Partial<FieldDef> & {internal_only?: boolean}}
	| {type: "updateSection"; id: string; patch: Partial<SectionDef>}
	| {type: "setTitle"; title: string}
	| {type: "appearance"; value: Record<string, string>}
	| {type: "references"; value: Definition["references"]}
	| {type: "appendReference"; value: NonNullable<Definition["references"]>[number]};
function mentions(value: unknown, ids: string[]): boolean {
	if (!value || typeof value !== "object") return false;
	if ("field" in value && ids.includes(String(value.field))) return true;
	return Object.values(value).some(v => mentions(v, ids));
}
export function dependencies(def: Definition, ids: string[]): string[] {
	const out: string[] = [];
	for (const section of def.sections) {
		if (mentions(section.show, ids)) out.push(`${section.title}: Show when`);
		for (const f of section.fields) {
			for (const [key, label] of [["show", "Show when"], ["required_when", "Required when"], ["outcomes", "Outcomes"]] as const)
				if (mentions(f[key], ids)) out.push(`${f.label}: ${label}`);
			if (ids.includes(String(f.config?.signer_from))) out.push(`${f.label}: Signer`);
		}
	}
	return out;
}
function clean(def: Definition, ids: string[]) {
	for (const s of def.sections) {
		if (mentions(s.show, ids)) delete s.show;
		for (const f of s.fields) {
			if (mentions(f.show, ids)) delete f.show;
			if (mentions(f.required_when, ids)) delete f.required_when;
			f.outcomes = f.outcomes?.filter(o => !mentions(o.when, ids));
			if (f.config && ids.includes(String(f.config.signer_from))) delete f.config.signer_from;
		}
	}
	for (const ref of def.references ?? []) ref.show_in = ref.show_in.filter(id => !ids.includes(id));
}
/** Allocate identities at the command boundary, keeping the reducer deterministic. */
export function prepareAction(def: Definition, action: Action): Action {
	if ((action.type !== "duplicateField" && action.type !== "duplicateSection") || action.ids) return action;
	const section = def.sections.find(s => s.id === action.id);
	const fields = action.type === "duplicateSection" ? section?.fields ?? [] : def.sections.flatMap(s => s.fields).filter(f => f.id === action.id);
	const ids: Record<string, string> = {};
	if (section && action.type === "duplicateSection") ids[section.id] = newId("s");
	for (const field of fields) {
		ids[field.id] = newId("f");
		for (const col of (field.config?.columns ?? []) as ColumnDef[]) ids[col.id] = newId("f");
	}
	return {...action, ids};
}
export function reduce(original: BuilderDefinition, action: Action): BuilderDefinition {
	const def = structuredClone(original);
	const section = "id" in action ? def.sections.find(s => s.id === action.id) : undefined;
	const owner = "id" in action ? def.sections.find(s => s.fields.some(f => f.id === action.id)) : undefined;
	const index = owner && "id" in action ? owner.fields.findIndex(f => f.id === action.id) : -1;
	const keys = new Set(def.sections.flatMap(s => s.fields.flatMap(f => [f.key, ...((f.config?.columns ?? []) as (ColumnDef & {key?: string})[]).map(c => c.key).filter((key): key is string => !!key)])));
	function copyField(field: FieldDef, mapping: Record<string, string>) {
		const copy = structuredClone(field); copy.id = mapping[field.id];
		let key = `${copy.key}_copy`; while (keys.has(key)) key += "_copy"; copy.key = key; keys.add(key);
		const columnMap: Record<string, string> = {};
		for (const col of (copy.config?.columns ?? []) as ColumnDef[]) {const old = col.id; col.id = mapping[old]; columnMap[old] = col.id; const keyed = col as ColumnDef & {key?: string}; if (keyed.key) {let key = `${keyed.key}_copy`; while (keys.has(key)) key += "_copy"; keyed.key = key; keys.add(key);}}
		if (copy.config?.fixed_rows) {const fixed = copy.config.fixed_rows as {column: string}; fixed.column = columnMap[fixed.column] ?? fixed.column;}
		function remap(v: unknown): unknown {
			if (typeof v === "string") return mapping[v] ?? v;
			if (Array.isArray(v)) return v.map(remap);
			if (v && typeof v === "object") return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, remap(x)]));
			return v;
		}
		return remap(copy) as FieldDef;
	}
	switch (action.type) {
		case "setTitle": def.title = action.title; break;
		case "appearance": def.appearance = action.value; break;
		case "references": def.references = action.value; break;
		case "appendReference": def.references = replaceReference(def.references ?? [], action.value); break;
		case "addSection": def.sections.push(structuredClone(action.section)); break;
		case "updateSection": if (section) Object.assign(section, action.patch); break;
		case "moveSection": if (section) {def.sections.splice(def.sections.indexOf(section), 1); def.sections.splice(action.index, 0, section);} break;
		case "duplicateSection": if (section) {
			if (!action.ids) throw new Error("Duplicate actions require prepareAction");
			const map = action.ids;
			const copy = {...structuredClone(section), id: map[section.id], fields: section.fields.map(f => copyField(f, map))};
			def.sections.splice(def.sections.indexOf(section) + 1, 0, copy);
		} break;
		case "deleteSection": if (section) {def.sections = def.sections.filter(s => s !== section); clean(def, [section.id, ...section.fields.map(f => f.id)]);} break;
		case "addField": {const target = def.sections.find(s => s.id === action.section); target?.fields.splice(action.index ?? target.fields.length, 0, structuredClone(action.field)); break;}
		case "updateField": if (owner) Object.assign(owner.fields[index], action.patch); break;
		case "duplicateField": if (owner) {if (!action.ids) throw new Error("Duplicate actions require prepareAction"); owner.fields.splice(index + 1, 0, copyField(owner.fields[index], action.ids));} break;
		case "deleteField": if (owner) {owner.fields.splice(index, 1); clean(def, [action.id]);} break;
		case "moveField": if (owner) {const [field] = owner.fields.splice(index, 1); def.sections.find(s => s.id === action.section)?.fields.splice(action.index, 0, field);} break;
	}
	return def;
}
export class History {
	current: BuilderDefinition;
	private past: BuilderDefinition[] = [];
	private future: BuilderDefinition[] = [];
	constructor(def: BuilderDefinition) {this.current = structuredClone(def);}
	get canUndo() {return this.past.length > 0;}
	get canRedo() {return this.future.length > 0;}
	apply(action: Action) {this.past.push(this.current); this.current = reduce(this.current, prepareAction(this.current, action)); this.future = []; return this.current;}
	undo() {if (this.canUndo) {this.future.push(this.current); this.current = this.past.pop()!;} return this.current;}
	redo() {if (this.canRedo) {this.past.push(this.current); this.current = this.future.pop()!;} return this.current;}
}
