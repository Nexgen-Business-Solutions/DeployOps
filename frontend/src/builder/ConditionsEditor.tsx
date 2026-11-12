import { useState } from "react";
import { conditionDepthAllowed } from "./safety";
import { operators, makePredicate } from "./conditions";
import type { Rule, Op } from "../forms/rules";
import type { FieldDef } from "../forms/types";
export function ConditionsEditor({label, value, fields, onChange, depth = 0}: {label: string; value?: Rule | null; fields: FieldDef[]; onChange: (value: Rule | undefined) => void; depth?: number}) {
	function seed(): Rule {return {field: fields[0]?.id ?? "", op: "eq", value: ""};}
	const kind = !value ? "none" : "field" in value ? "condition" : "all" in value ? "all" : "any" in value ? "any" : "not";
	const condition = value && "field" in value ? value : undefined;
	const selected = fields.find(f => f.id === condition?.field);
	function change(op: Op, raw: string, id = condition?.field ?? fields[0]?.id ?? "") {onChange(makePredicate(id, op, raw, fields.find(f => f.id === id)?.type ?? "text"));}
	return <fieldset className="my-3 min-w-0 rounded border p-2"><legend>{label}</legend>
		<select aria-label={`${label} group`} value={kind} onChange={e => {
			const k = e.target.value; onChange(k === "none" ? undefined : k === "condition" ? seed() : k === "not" ? {not: seed()} : k === "all" ? {all: [seed()]} : {any: [seed()]});
		}}><option value="none">No condition</option><option value="condition" disabled={!fields.length}>Condition</option>{conditionDepthAllowed(depth) && <><option value="all" disabled={!fields.length}>All of</option><option value="any" disabled={!fields.length}>Any of</option><option value="not" disabled={!fields.length}>Not</option></>}</select>
		{condition && <div className="space-y-2">
			<select aria-label={`${label} field`} value={condition.field} onChange={e => change(condition.op, "", e.target.value)}>{!selected && <option value={condition.field}>Choose earlier field</option>}{fields.map(f => <option key={f.id} value={f.id}>{f.label}</option>)}</select>
			<select aria-label={`${label} operator`} value={condition.op} onChange={e => change(e.target.value as Op, String(condition.value ?? ""))}>{operators.map(([op, text]) => <option key={op} value={op}>{text}</option>)}</select>
			{!["empty", "not_empty"].includes(condition.op) && (choices(selected) && !["in", "not_in"].includes(condition.op) ? <select aria-label={`${label} value`} value={String(condition.value ?? "")} onChange={e => change(condition.op, e.target.value)}><option value="" disabled>Choose an answer</option>{choices(selected)!.map(o => <option key={o} value={o}>{o}</option>)}</select> : selected?.type === "checkbox" && !["in", "not_in"].includes(condition.op) ? <select aria-label={`${label} value`} value={String(condition.value ?? false)} onChange={e => change(condition.op, e.target.value)}><option value="true">True</option><option value="false">False</option></select> : <ConditionValue key={`${condition.field}:${condition.op}`} label={`${label} value`} numeric={selected?.type === "number" || selected?.type === "currency"} placeholder={condition.op === "in" || condition.op === "not_in" ? "Comma separated values" : "Value"} value={Array.isArray(condition.value) ? condition.value.join(", ") : String(condition.value ?? "")} onCommit={raw => change(condition.op, raw)} />)}
		</div>}
		{value && "not" in value && <ConditionsEditor label="Not" fields={fields} depth={depth + 1} value={value.not} onChange={r => onChange(r ? {not: r} : undefined)} />}
		{value && ("all" in value || "any" in value) && (() => {const group = "all" in value ? value.all : value.any; const wrap = (rules: Rule[]): Rule => "all" in value ? {all: rules} : {any: rules}; return <>
			{group.map((rule, index) => <ConditionsEditor key={index} label={`Condition ${index + 1}`} fields={fields} depth={depth + 1} value={rule} onChange={r => onChange(wrap(group.flatMap((item, i) => i === index ? r ? [r] : [] : [item])))} />)}
			<button type="button" onClick={() => onChange(wrap([...group, seed()]))}>Add condition</button>
		</>;})()}
	</fieldset>;
}

/** The answers a choice-like field can have, so a condition picks one instead of typing it. */
function choices(field?: FieldDef): string[] | undefined {
	if (!field) return undefined;
	if (field.type === "yes_no") return ["Yes", "No"];
	if (field.type === "choice" || field.type === "multi_check") return ((field.config?.options ?? []) as string[]).filter(o => o.trim());
	return undefined;
}

function ConditionValue({label, numeric, value, placeholder, onCommit}: {label: string; numeric: boolean; value: string; placeholder: string; onCommit: (raw: string) => void}) {
	const [raw, setRaw] = useState(value);
	return <input aria-label={label} inputMode={numeric ? "decimal" : undefined} placeholder={placeholder} value={numeric ? raw : value} onChange={e => {setRaw(e.target.value); if (!numeric) onCommit(e.target.value);}} onBlur={() => {if (numeric) onCommit(raw);}} />;
}
