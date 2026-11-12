// Choice options as a list: one growing box per option, reorder, delete, paste many, bulk edit.
import { ArrowDown, ArrowUp, ListPlus, Maximize2, Plus, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Btn, IconBtn, Modal } from "./kit";

export function OptionsEditor({options, onChange, label = "Options"}: {options: string[]; onChange: (value: string[]) => void; label?: string}) {
	const refs = useRef<(HTMLTextAreaElement | null)[]>([]);
	const [focus, setFocus] = useState<number>();
	const [bulk, setBulk] = useState(false);
	useEffect(() => {if (focus !== undefined) {refs.current[focus]?.focus(); setFocus(undefined);}}, [focus]);
	const rows = options.length ? options : [];
	const set = (i: number, value: string) => onChange(rows.map((o, j) => (j === i ? value : o)));
	const insert = (at: number, values: string[]) => {onChange([...rows.slice(0, at), ...values, ...rows.slice(at)]); setFocus(at + values.length - 1);};
	const remove = (i: number) => {onChange(rows.filter((_, j) => j !== i)); setFocus(Math.max(0, i - 1));};
	const move = (i: number, to: number) => {const next = [...rows]; const [item] = next.splice(i, 1); next.splice(to, 0, item); onChange(next); setFocus(to);};
	const counts = rows.reduce<Record<string, number>>((acc, o) => {const k = o.trim().toLowerCase(); if (k) acc[k] = (acc[k] ?? 0) + 1; return acc;}, {});
	return <div className="space-y-2">
		<div className="flex items-center justify-between"><span className="text-[13px] font-medium text-slate-700">{label} <span className="font-normal text-slate-400">({rows.filter(o => o.trim()).length})</span></span>
			<button type="button" className="!h-7 !px-2 !text-xs" onClick={() => setBulk(true)}><Maximize2 className="size-3" />Bulk edit</button></div>
		{rows.length === 0 && <p className="rounded-lg border border-dashed border-slate-300 px-3 py-4 text-center text-xs text-slate-500">No options yet.</p>}
		<ol className="space-y-1.5">{rows.map((option, i) => {
			const duplicate = !!option.trim() && counts[option.trim().toLowerCase()] > 1;
			return <li key={i} className="group relative flex items-start gap-1">
				<span className="mt-[7px] w-4 shrink-0 text-right text-[11px] tabular-nums text-slate-400">{i + 1}</span>
				<div className="min-w-0 flex-1">
					<textarea ref={el => {refs.current[i] = el;}} rows={1} aria-label={`Option ${i + 1}`} value={option} placeholder="Option text"
						className={`!mt-0 !min-h-0 block w-full resize-none rounded-lg border bg-white px-2.5 py-1.5 text-[13px] leading-snug [field-sizing:content] focus:outline-none focus:ring-3 ${duplicate ? "border-amber-400 focus:ring-amber-200" : "border-slate-300 focus:border-brand-500 focus:ring-brand-500/15"}`}
						onChange={e => set(i, e.target.value.replace(/\n/g, " "))}
						onKeyDown={e => {
							if (e.key === "Enter") {e.preventDefault(); insert(i + 1, [""]);}
							else if (e.key === "Backspace" && option === "" && rows.length > 1) {e.preventDefault(); remove(i);}
							else if (e.altKey && e.key === "ArrowUp" && i > 0) {e.preventDefault(); move(i, i - 1);}
							else if (e.altKey && e.key === "ArrowDown" && i < rows.length - 1) {e.preventDefault(); move(i, i + 1);}
						}}
						onPaste={e => {
							const lines = e.clipboardData.getData("text").split(/\r?\n/).map(l => l.trim()).filter(Boolean);
							if (lines.length < 2) return;
							e.preventDefault();
							const next = [...rows]; next.splice(i, option ? 0 : 1, ...lines); onChange(next); setFocus(i + lines.length - (option ? 0 : 1));
						}} />
					{duplicate && <p className="mt-0.5 text-[11px] text-amber-700">Duplicate option</p>}
				</div>
				<div className="pointer-events-none absolute -top-2.5 right-1.5 z-10 flex rounded-md bg-white opacity-0 shadow-sm ring-1 ring-slate-200 transition group-hover:pointer-events-auto group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:opacity-100">
					<IconBtn label={`Move option ${i + 1} up`} className="!h-6 !w-6 !rounded-md !p-0 !shadow-none !ring-0" disabled={i === 0} onClick={() => move(i, i - 1)}><ArrowUp className="size-3.5" /></IconBtn>
					<IconBtn label={`Move option ${i + 1} down`} className="!h-6 !w-6 !rounded-md !p-0 !shadow-none !ring-0" disabled={i === rows.length - 1} onClick={() => move(i, i + 1)}><ArrowDown className="size-3.5" /></IconBtn>
					<IconBtn label={`Delete option ${i + 1}`} className="!h-6 !w-6 !rounded-md !p-0 !shadow-none !ring-0 hover:!bg-red-50 hover:!text-red-600" onClick={() => remove(i)}><X className="size-3.5" /></IconBtn>
				</div>
			</li>;
		})}</ol>
		<button type="button" className="w-full justify-center !border-dashed" onClick={() => insert(rows.length, [""])}><Plus className="size-3.5" />Add option</button>
		<p className="text-[11px] leading-snug text-slate-400">Enter adds the next option. Paste several lines to add many at once. Alt+↑/↓ reorders.</p>
		{bulk && <BulkEdit options={rows} onClose={() => setBulk(false)} onApply={value => {onChange(value); setBulk(false);}} />}
	</div>;
}

function BulkEdit({options, onApply, onClose}: {options: string[]; onApply: (value: string[]) => void; onClose: () => void}) {
	const [text, setText] = useState(options.join("\n"));
	const parsed = text.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
	return <Modal open size="lg" title="Edit all options" description="One option per line. Blank lines are ignored." onClose={onClose}
		footer={<><span className="mr-auto text-sm text-slate-500">{parsed.length} option{parsed.length === 1 ? "" : "s"}</span><Btn onClick={onClose}>Cancel</Btn><Btn tone="primary" icon={<ListPlus className="size-4" />} onClick={() => onApply(parsed)}>Apply</Btn></>}>
		<textarea autoFocus className="bld-input min-h-[22rem] font-normal leading-relaxed" value={text} onChange={e => setText(e.target.value)} />
	</Modal>;
}
