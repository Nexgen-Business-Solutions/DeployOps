import { getPlugin, type FieldInputProps } from "./index";
import type { ColumnDef, TableRow } from "../types";
import { newRowId } from "../logic";
export function TableInput({ field, value, disabled, ctx, onChange, inputId }: FieldInputProps) {
	const config = field.config ?? {}, columns = (config.columns ?? []) as ColumnDef[], rows = (value ?? []) as TableRow[];
	const fixed = config.fixed_rows as {
		column: string;
		labels: string[];
	} | undefined;
	return <div className="space-y-3">{Number(config.min_rows) > 0 && <p className="text-sm text-muted">Add at least {Number(config.min_rows)} rows</p>}{rows.map((row, index) => <div key={row._row} className={fixed ? "border-b border-line py-3" : "rounded-2xl bg-zinc-50 p-3"}><div className="mb-2 flex justify-between"><span className="text-sm text-muted">{fixed ? String(row[fixed.column] ?? "") : `#${index + 1}`}</span>{!fixed && !disabled && <button type="button" aria-label="Remove row" onClick={() => onChange(rows.filter((_, i) => i !== index))}>Remove</button>}</div><div className={fixed ? "grid gap-2 sm:grid-cols-2" : "space-y-3"}>{columns.map(col => { const Plugin = getPlugin(col.type).Input; return <div key={col.id}><label className="text-sm text-muted" htmlFor={`${inputId}-${row._row}-${col.id}`}>{col.label}</label><Plugin field={col} value={row[col.id]} disabled={disabled || fixed?.column === col.id} invalid={false} inputId={`${inputId}-${row._row}-${col.id}`} compact ctx={ctx} onChange={v => onChange(rows.map((r, i) => i === index ? { ...r, [col.id]: v } : r))} /></div>; })}</div></div>)}{!fixed && !disabled && <button type="button" className="text-brand-500 font-medium" onClick={() => onChange([...rows, { _row: newRowId() }])}>+ Add row</button>}</div>;
}
