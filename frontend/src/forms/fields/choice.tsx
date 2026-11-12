import { choiceFromInput, otherOption } from "./convert";
import { useState } from "react";
import { CheckRow, RadioList, Segmented } from "../../components/form/controls";
import type { FieldInputProps } from "./index";
export function ChoiceInput({ field, value, disabled, inputId, onChange, compact }: FieldInputProps) {
	const c = field.config ?? {}, options = (c.options ?? []) as string[];
	const other = typeof value === "object" && value !== null;
	const [editingOther, setEditingOther] = useState(false);
	const [draft, setDraft] = useState("");
	const shownOther = other || editingOther;
	const otherLabel = c.allow_other ? otherOption(options) : null;
	const all = otherLabel ? [...options, otherLabel] : options;
	const selected = shownOther ? otherLabel : typeof value === "string" ? value : null;
	function choose(v: string | null) {
		setEditingOther(otherLabel !== null && v === otherLabel);
		onChange(choiceFromInput(v, otherLabel, draft));
	}
	return <div className="space-y-3">{c.display === "buttons" ? (all.length <= 3 && all.every(o => o.length < 20) ? <Segmented options={all} value={selected} disabled={disabled} onChange={choose} small={compact} /> : <RadioList options={all} value={selected} disabled={disabled} onChange={choose} />) : <select id={inputId} aria-label={field.label} className="field-input" disabled={disabled} value={selected ?? ""} onChange={e => choose(e.target.value || null)}><option value="">Select…</option>{all.map(o => <option key={o}>{o}</option>)}</select>}
		{shownOther && <input aria-label={`${field.label}: Other`} className="field-input" disabled={disabled} placeholder="Never type passwords, PINs, OTPs or pairing codes." value={other ? String((value as {
			other: string;
		}).other ?? "") : draft} onChange={e => { setDraft(e.target.value); onChange(e.target.value.trim() ? { other: e.target.value } : null); }} />}</div>;
}
export function MultiCheckInput({ field, value, disabled, onChange }: FieldInputProps) {
	const c = field.config ?? {}, current = (value ?? { selected: [], other: null }) as {
		selected: string[];
		other: string | null;
	};
	const options = (c.options ?? []) as string[];
	return <div>{options.map(o => <CheckRow key={o} label={o} checked={current.selected.includes(o)} disabled={disabled} onChange={yes => onChange({ ...current, selected: yes ? [...current.selected, o] : current.selected.filter(v => v !== o) })} />)}{c.allow_other === true && <label className="block text-sm">Other<input className="field-input mt-2" disabled={disabled} value={current.other ?? ""} placeholder="Never type passwords, PINs, OTPs or pairing codes." onChange={e => onChange({ ...current, other: e.target.value || null })} /></label>}</div>;
}
