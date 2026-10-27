import { Plus, Trash2 } from "lucide-react";

import { toInputTime } from "../../lib/form";
import type { Column, Row, TableInfo } from "../../lib/types";
import { Segmented } from "./controls";

function Cell({ column, row, disabled, onChange }: { column: Column; row: Row; disabled: boolean; onChange: (value: string | number | null) => void }) {
	const value = row[column.fieldname];
	if (column.fieldtype === "Select" && column.options.length <= 3) {
		return <Segmented options={column.options} value={(value as string) ?? null} disabled={disabled} onChange={onChange} small />;
	}
	if (column.fieldtype === "Select") {
		return (
			<select className="field-input py-2.5" value={(value as string) ?? ""} disabled={disabled} onChange={(e) => onChange(e.target.value || null)}>
				<option value="">Select…</option>
				{column.options.map((option) => (
					<option key={option}>{option}</option>
				))}
			</select>
		);
	}
	if (column.fieldtype === "Check") {
		return (
			<button
				type="button"
				disabled={disabled}
				aria-pressed={Boolean(value)}
				onClick={() => onChange(value ? 0 : 1)}
				className={`h-8 rounded-full px-3 text-[13px] font-medium transition ${value ? "bg-ink text-white" : "bg-zinc-100 text-muted hover:text-ink"}`}
			>
				{column.label}
			</button>
		);
	}
	const type = { Time: "time", Date: "date" }[column.fieldtype] ?? "text";
	return (
		<input
			className="field-input py-2.5"
			type={type}
			aria-label={column.label}
			placeholder={column.label}
			value={type === "time" ? toInputTime(value) : ((value as string) ?? "")}
			disabled={disabled}
			onChange={(e) => onChange(e.target.value || null)}
		/>
	);
}

/** Fixed rows (opening hours, maintenance tasks) or free rows (trainees, actions). */
export function TableField({ table, rows, disabled, onChange }: { table: TableInfo; rows: Row[]; disabled: boolean; onChange: (rows: Row[]) => void }) {
	const fixed = table.kind === "grid";
	const labelColumn = fixed ? table.columns.find((c) => c.read_only) : undefined;
	const editable = table.columns.filter((c) => !c.read_only);

	function update(index: number, fieldname: string, value: string | number | null) {
		onChange(rows.map((row, i) => (i === index ? { ...row, [fieldname]: value } : row)));
	}

	if (fixed) {
		const closed = editable.find((c) => c.fieldname === "closed");
		return (
			<ul className="divide-y divide-line border-y border-line">
				{rows.map((row, index) => {
					const isClosed = Boolean(closed && row.closed);
					return (
						<li key={String(row.name ?? index)} className="py-3">
							<div className="flex items-center justify-between gap-3">
								<span className="text-[15px]">{labelColumn ? String(row[labelColumn.fieldname] ?? "") : index + 1}</span>
								{closed && <Cell column={closed} row={row} disabled={disabled} onChange={(v) => update(index, closed.fieldname, v)} />}
							</div>
							{!isClosed && (
								<div className={`mt-2 grid gap-2 ${editable.length - (closed ? 1 : 0) > 1 ? "grid-cols-2" : ""}`}>
									{editable
										.filter((c) => c !== closed)
										.map((column) => (
											<Cell key={column.fieldname} column={column} row={row} disabled={disabled} onChange={(v) => update(index, column.fieldname, v)} />
										))}
								</div>
							)}
						</li>
					);
				})}
			</ul>
		);
	}

	return (
		<div className="space-y-3">
			{rows.map((row, index) => (
				<div key={String(row.name ?? index)} className="rounded-2xl bg-zinc-50 p-3">
					<div className="mb-2 flex items-center justify-between">
						<span className="text-[13px] font-medium text-muted">#{index + 1}</span>
						{!disabled && (
							<button type="button" onClick={() => onChange(rows.filter((_, i) => i !== index))} className="text-muted hover:text-red-600" aria-label="Remove row">
								<Trash2 className="size-4" />
							</button>
						)}
					</div>
					<div className="space-y-2">
						{editable.map((column) => (
							<div key={column.fieldname}>
								{column.fieldtype === "Select" && <p className="mb-1 text-[13px] text-muted">{column.label}</p>}
								<Cell column={column} row={row} disabled={disabled} onChange={(v) => update(index, column.fieldname, v)} />
							</div>
						))}
					</div>
				</div>
			))}
			{!disabled && (
				<button type="button" onClick={() => onChange([...rows, {}])} className="inline-flex items-center gap-1.5 text-[15px] font-medium text-brand-500">
					<Plus className="size-4" /> Add
				</button>
			)}
		</div>
	);
}
