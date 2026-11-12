import type { FieldDef, Definition, ColumnDef } from "../forms/types";
import { getPlugin } from "../forms/fields";
import { ConditionsEditor } from "./ConditionsEditor";
import { earlierFields } from "./conditions";
import type { Catalog } from "./api";
import { newId } from "./ids";
import { OptionsEditor } from "./OptionsEditor";
import { FieldIcon, fieldLabel } from "./fieldIcons";
type Patch = Partial<FieldDef> & {internal_only?: boolean};
const labels: Record<string, string> = {max_length: "Max length", min: "Minimum", max: "Maximum", decimal: "Decimal", currency: "Currency", min_selected: "Minimum selected", must_tick: "Must be ticked", captions: "Captions", min_rows: "Minimum rows", text: "Note text"};
const settings: Record<string, string[]> = {text: ["max_length"], number: ["min", "max", "decimal"], currency: ["currency"], choice: ["allow_other", "display"], multi_check: ["min_selected", "allow_other"], checkbox: ["must_tick"], photos: ["min", "max", "captions"], files: ["min", "max", "extensions"], table: ["min_rows"], info: ["text"], signature: ["signer_from"]};
export function SettingsPanel({field, definition, catalog, onChange}: {field: FieldDef; definition: Definition; catalog: Catalog; onChange: (patch: Patch) => void}) {
	const fields = earlierFields(definition, field.id); const c = field.config ?? {};
	const config = (key: string, value: unknown) => {const next = {...c}; if (value === undefined) delete next[key]; else next[key] = value; onChange({config: next});};
	const duplicate = definition.sections.flatMap(s => s.fields).some(f => f.id !== field.id && f.key === field.key);
	return <div className="bld-form"><div className="flex items-center gap-2.5 border-b border-slate-200 pb-3"><span className="grid size-8 place-items-center rounded-md bg-brand-50 text-brand-600"><FieldIcon type={field.type} /></span><div><h2 className="text-sm font-semibold text-slate-900">{fieldLabel(field.type)}</h2><p className="text-xs text-slate-500">Field settings</p></div></div>
		<h3>General</h3>
		<label className="block">Label<input value={field.label} onChange={e => {const label = e.target.value; onChange(isAutoKey(field.key, field.label) ? {label, key: keyFor(label, definition, field.id)} : {label});}} /></label>
		<label className="block">Help text<textarea value={field.help ?? ""} onChange={e => onChange({help: e.target.value})} /></label>
		<label className="block">Key <span className="font-normal text-slate-400">· used in exports and reports</span><input className="font-mono" pattern="[a-z][a-z0-9_]*" value={field.key} onChange={e => onChange({key: e.target.value})} /></label>{(duplicate || !/^[a-z][a-z0-9_]*$/.test(field.key)) && <p role="alert">Use a unique lowercase slug.</p>}
		<label><input type="checkbox" checked={!!field.required} onChange={e => onChange({required: e.target.checked})} /> Required</label>
		<h3>Logic</h3>
		<ConditionsEditor label="Show when" fields={fields} value={field.show} onChange={show => onChange({show})} />
		<ConditionsEditor label="Required when" fields={fields} value={field.required_when} onChange={required_when => onChange({required_when})} />
		<h3>{fieldLabel(field.type)} options</h3>
		{!(settings[field.type]?.length) && !["choice", "table"].includes(field.type) && <p className="text-[13px] text-slate-500">No additional settings</p>}
		{(settings[field.type] ?? []).map(key => {
			if (["decimal", "must_tick", "captions", "allow_other"].includes(key)) return <label key={key}><input type="checkbox" checked={c[key] === undefined ? key === "decimal" : !!c[key]} onChange={e => config(key, e.target.checked)} />{key === "allow_other" ? "Allow Other" : labels[key]}</label>;
			if (key === "display") return <label className="block" key={key}>Display<select value={String(c.display ?? "dropdown")} onChange={e => config(key, e.target.value)}><option value="dropdown">Drop-down</option><option value="buttons">Buttons</option></select></label>;
			if (key === "signer_from") return <label className="block" key={key}>Signer from<select value={String(c.signer_from ?? "")} onChange={e => config(key, e.target.value || undefined)}><option value="">Signer name</option><option value="context:technician">Job technician</option>{fields.map(f => <option key={f.id} value={f.id}>{f.label}</option>)}</select></label>;
			if (key === "extensions") return <label className="block" key={key}>Extensions<input value={((c.extensions ?? []) as string[]).join(", ")} onChange={e => config(key, e.target.value.split(",").map(v => v.trim()).filter(Boolean))} /></label>;
			if (key === "min_selected") {const total = ((c.options ?? []) as string[]).filter(o => o.trim()).length; return <div key={key} className="flex items-end gap-2"><label className="min-w-0 flex-1">{labels[key]}<input type="number" min={0} max={total || undefined} value={String(c[key] ?? "")} onChange={e => config(key, e.target.value === "" ? undefined : Number(e.target.value))} /></label><button type="button" className="mb-0.5" disabled={!total || c[key] === total} onClick={() => config(key, total)}>Require all ({total})</button></div>;}
			const numeric = !["currency", "text"].includes(key);
			return <label className="block" key={key}>{labels[key]}<input type={numeric ? "number" : "text"} value={String(c[key] ?? "")} onChange={e => config(key, e.target.value === "" ? undefined : numeric ? Number(e.target.value) : e.target.value)} /></label>;
		})}
		{["choice", "multi_check"].includes(field.type) && <Options options={(c.options ?? []) as string[]} onChange={value => config("options", value)} />}
		{field.type === "table" && <TableSettings field={field} fields={fields} onChange={value => onChange({config: value})} />}
		<h3>Advanced</h3>
		<label className="block">Fill from<select value={field.fill_from?.value ?? ""} onChange={e => onChange({fill_from: e.target.value ? {value: e.target.value, locked: field.fill_from?.locked ?? true} : undefined})}><option value="">{catalog.values.length ? "Nothing (blank)" : "Not available for this form"}</option>{catalog.values.map(v => <option key={v.value} value={v.value}>{v.label}</option>)}</select></label>
		{field.fill_from && <label><input type="checkbox" checked={!!field.fill_from.locked} onChange={e => onChange({fill_from: {...field.fill_from!, locked: e.target.checked}})} />Locked (otherwise editable)</label>}
		{catalog.outcomes.length > 0 && <fieldset><legend>Outcomes</legend>{field.outcomes?.map((outcome, i) => <div key={i}>
			<ConditionsEditor label={`Outcome ${i + 1}`} fields={fields} value={outcome.when} onChange={when => onChange({outcomes: when ? field.outcomes!.map((o, j) => j === i ? {...o, when} : o) : field.outcomes!.filter((_, j) => j !== i)})} />
			<select aria-label="Outcome effect" value={outcome.effect} onChange={e => onChange({outcomes: field.outcomes!.map((o, j) => j === i ? {...o, effect: e.target.value} : o)})}>{catalog.outcomes.map(o => <option key={o.effect} value={o.effect}>{o.label}</option>)}</select>
			<button onClick={() => onChange({outcomes: field.outcomes!.filter((_, j) => j !== i)})}>Remove outcome</button>
		</div>)}<button disabled={!fields.length || !catalog.outcomes.length} onClick={() => onChange({outcomes: [...(field.outcomes ?? []), {when: {field: fields[0].id, op: "not_empty"}, effect: catalog.outcomes[0].effect}]})}>Add outcome</button></fieldset>}
		<label><input type="checkbox" checked={!!(field as FieldDef & {internal_only?: boolean}).internal_only} onChange={e => onChange({internal_only: e.target.checked})} />Internal only (hidden from customer PDFs)</label>
	</div>;
}
/** A key the designer hasn't typed: the builder's placeholder or the slug of the current label. */
export function isAutoKey(key: string, label: string): boolean {
	return /^field_[a-z0-9]{6}$/.test(key) || key === slug(label) || /^[a-z][a-z0-9_]*_\d+$/.test(key) && key.replace(/_\d+$/, "") === slug(label);
}
export function slug(label: string): string {
	const s = label.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 40).replace(/_+$/, "");
	return /^[a-z]/.test(s) ? s : s ? `f_${s}` : "";
}
/** The label's slug, made unique among the form's other keys. */
export function keyFor(label: string, definition: Definition, id: string): string {
	const base = slug(label);
	if (!base) return `field_${id.slice(2)}`;
	const taken = new Set(definition.sections.flatMap(s => s.fields).filter(f => f.id !== id).map(f => f.key));
	let key = base, n = 2;
	while (taken.has(key)) key = `${base}_${n++}`;
	return key;
}
function Options({options, onChange}: {options: string[]; onChange: (value: string[]) => void}) {
	return <OptionsEditor options={options} onChange={onChange} />;
}
function TableSettings({field, fields, onChange}: {field: FieldDef; fields: FieldDef[]; onChange: (config: Record<string, unknown>) => void}) {
	const c = field.config ?? {}, columns = (c.columns ?? []) as ColumnDef[];
	const fixed = c.fixed_rows as {column: string; labels: string[]} | undefined;
	function update(i: number, patch: Partial<ColumnDef>) {onChange({...c, columns: columns.map((col, j) => j === i ? {...col, ...patch} : col)});}
	return <fieldset><legend>Columns</legend>{columns.map((col, i) => <div key={col.id} className="my-2 border p-2">
		<label>Column label<input value={col.label} onChange={e => update(i, {label: e.target.value})} /></label>
		<select aria-label="Column type" value={col.type} onChange={e => update(i, {type: e.target.value, config: structuredClone(getPlugin(e.target.value).defaultConfig)})}>{["text", "long_text", "number", "currency", "choice", "multi_check", "checkbox", "yes_no", "date", "time", "datetime"].filter(t => getPlugin(t).inTable).map(t => <option key={t}>{t}</option>)}</select>
		<label><input type="checkbox" checked={!!col.required} onChange={e => update(i, {required: e.target.checked})} />Required column</label>
		{["choice", "multi_check"].includes(col.type) && <Options options={(col.config?.options ?? []) as string[]} onChange={options => update(i, {config: {...col.config, options}})} />}
		{col.type === "number" && <>{["min", "max"].map(key => <label key={key}>{key}<input type="number" value={String(col.config?.[key] ?? "")} onChange={e => update(i, {config: {...col.config, [key]: e.target.value === "" ? undefined : Number(e.target.value)}})} /></label>)}</>}
		{col.type === "text" && <label>Max length<input type="number" value={String(col.config?.max_length ?? "")} onChange={e => update(i, {config: {...col.config, max_length: e.target.value ? Number(e.target.value) : undefined}})} /></label>}
		{col.type === "number" && <label><input type="checkbox" checked={col.config?.decimal !== false} onChange={e => update(i, {config: {...col.config, decimal: e.target.checked}})} />Decimal</label>}
		{col.type === "checkbox" && <label><input type="checkbox" checked={!!col.config?.must_tick} onChange={e => update(i, {config: {...col.config, must_tick: e.target.checked}})} />Must be ticked</label>}
		{col.type === "choice" && <><label>Display<select value={String(col.config?.display ?? "dropdown")} onChange={e => update(i, {config: {...col.config, display: e.target.value}})}><option value="dropdown">Drop-down</option><option value="buttons">Buttons</option></select></label><label><input type="checkbox" checked={!!col.config?.allow_other} onChange={e => update(i, {config: {...col.config, allow_other: e.target.checked}})} />Allow Other</label></>}
		<button onClick={() => onChange({...c, columns: columns.filter((_, j) => j !== i), ...(fixed?.column === col.id ? {fixed_rows: undefined} : {})})}>Delete column</button>
	</div>)}<button onClick={() => onChange({...c, columns: [...columns, {id: newId("f"), label: "Column", type: "text"}]})}>Add column</button>
		<label><input type="checkbox" checked={!!fixed} disabled={!columns.length} onChange={e => onChange({...c, fixed_rows: e.target.checked ? {column: columns[0].id, labels: []} : undefined})} />Fixed rows</label>
		{fixed && <><select aria-label="Fixed row label column" value={fixed.column} onChange={e => onChange({...c, fixed_rows: {...fixed, column: e.target.value}})}>{columns.map(col => <option key={col.id} value={col.id}>{col.label}</option>)}</select><label>Fixed row labels<textarea value={fixed.labels.join("\n")} onChange={e => onChange({...c, fixed_rows: {...fixed, labels: e.target.value.split("\n")}})} /></label></>}
		<span className="sr-only">{fields.length} earlier fields</span>
	</fieldset>;
}
