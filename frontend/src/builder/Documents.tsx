// Reference documents of a form: upload (several at once, or drop), rename, choose where each shows.
import { FileText, Plus, Trash2, UploadCloud, X } from "lucide-react";
import { useState } from "react";
import { uploadTo } from "../lib/api";
import type { Definition } from "../forms/types";
import { Alert, IconBtn } from "./kit";

type Ref = NonNullable<Definition["references"]>[number];

export function documentUrl(form: string, file: string): string {
	return `/api/method/forms_core.api.form_reference_file?form=${encodeURIComponent(form)}&file=${encodeURIComponent(file)}`;
}

export function Documents({form, definition, onChange, onAdd}: {form: string; definition: Definition; onAdd: (ref: Ref) => void; onChange: (refs: Definition["references"]) => void}) {
	const [error, setError] = useState(""), [busy, setBusy] = useState(0), [over, setOver] = useState(false);
	const refs = definition.references ?? [];
	const names = new Map<string, string>();
	for (const s of definition.sections) {
		names.set(s.id, `Step: ${s.title || "Untitled step"}`);
		for (const f of s.fields) names.set(f.id, `${f.label || f.key}`);
	}
	async function upload(files: File[]) {
		setError("");
		for (const file of files) {
			setBusy(n => n + 1);
			try {
				const url = await uploadTo<string>("forms_core.api.upload_reference", file, file.name, {form});
				const hash = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", await file.arrayBuffer())), n => n.toString(16).padStart(2, "0")).join("");
				onAdd({file: url, title: file.name.replace(/\.[a-z0-9]+$/i, ""), show_in: [], hash});
			} catch (e) {setError(`${file.name}: ${e instanceof Error ? e.message : String(e)}`);}
			finally {setBusy(n => n - 1);}
		}
	}
	const update = (i: number, patch: Partial<Ref>) => onChange(refs.map((r, j) => (i === j ? {...r, ...patch} : r)));
	return <div className="space-y-4">
		<div><h2 className="text-lg font-semibold text-slate-900">Reference documents</h2><p className="mt-1 text-sm text-slate-500">Manuals or drawings people can open while filling the form. Every document is in the form's documents panel; add it to a step or field to show it there too. Files stay private.</p></div>
		{error && <Alert>{error}</Alert>}
		<label onDragOver={e => {e.preventDefault(); setOver(true);}} onDragLeave={() => setOver(false)} onDrop={e => {e.preventDefault(); setOver(false); void upload([...e.dataTransfer.files]);}}
			className={`flex cursor-pointer items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-6 transition ${over ? "border-brand-500 bg-brand-50/50" : "border-slate-300 bg-white hover:border-slate-400"}`}>
			<UploadCloud className="size-6 text-slate-400" aria-hidden />
			<span className="text-sm"><span className="font-medium text-slate-800">{busy ? `Uploading ${busy} file${busy === 1 ? "" : "s"}…` : "Drop files here, or browse"}</span><span className="block text-xs text-slate-500">PDF, images or any file. You can pick several.</span></span>
			<input className="sr-only" aria-label="Attach reference document" type="file" multiple onChange={e => {void upload([...(e.target.files ?? [])]); e.target.value = "";}} />
		</label>
		{refs.length === 0 ? <p className="py-6 text-center text-sm text-slate-500">No documents yet.</p> :
		<ul className="space-y-3">{refs.map((ref, i) => {
			const unused = [...names.keys()].filter(id => !ref.show_in.includes(id));
			return <li key={`${ref.file}-${i}`} aria-label={`Document ${ref.title}`} className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
				<div className="flex items-center gap-3">
					<span className="grid size-9 shrink-0 place-items-center rounded-lg bg-red-50 text-red-600"><FileText className="size-4" /></span>
					<input aria-label="Document title" className="bld-input flex-1 font-medium" value={ref.title} onChange={e => update(i, {title: e.target.value})} />
					<a className="shrink-0 text-sm font-medium text-brand-600 hover:underline" href={documentUrl(form, ref.file)} target="_blank" rel="noreferrer">Open</a>
					<IconBtn label={`Remove ${ref.title}`} className="hover:!bg-red-50 hover:!text-red-600" onClick={() => onChange(refs.filter((_, j) => j !== i))}><Trash2 className="size-4" /></IconBtn>
				</div>
				<div className="mt-3 flex flex-wrap items-center gap-2 pl-12">
					<span className="text-xs font-medium uppercase tracking-wide text-slate-500">Shown on</span>
					{ref.show_in.length === 0 && <span className="text-xs text-slate-400">the documents panel only</span>}
					{ref.show_in.map(id => <span key={id} className={`inline-flex items-center gap-1 rounded-full py-0.5 pl-2.5 pr-1 text-xs font-medium ring-1 ring-inset ${names.has(id) ? "bg-slate-100 text-slate-700 ring-slate-200" : "bg-amber-50 text-amber-800 ring-amber-200"}`}>
						{names.get(id) ?? "Deleted step or field"}
						<button type="button" aria-label={`Stop showing on ${names.get(id) ?? id}`} className="grid size-4 place-items-center rounded-full hover:bg-slate-300/60" onClick={() => update(i, {show_in: ref.show_in.filter(x => x !== id)})}><X className="size-3" /></button>
					</span>)}
					{unused.length > 0 && <label className="relative inline-flex items-center">
						<Plus className="pointer-events-none absolute left-2 size-3 text-brand-600" />
						<select aria-label={`Add ${ref.title} to a step or field`} value="" onChange={e => e.target.value && update(i, {show_in: [...ref.show_in, e.target.value]})}
							className="h-7 cursor-pointer rounded-full border border-dashed border-slate-300 bg-white pl-6 pr-2 text-xs font-medium text-brand-600 hover:border-brand-500 focus:outline-none">
							<option value="">Add to a step or field…</option>
							{definition.sections.map(s => <optgroup key={s.id} label={s.title || "Untitled step"}>
								{unused.includes(s.id) && <option value={s.id}>The whole step</option>}
								{s.fields.filter(f => unused.includes(f.id)).map(f => <option key={f.id} value={f.id}>{f.label || f.key}</option>)}
							</optgroup>)}
						</select>
					</label>}
				</div>
			</li>;
		})}</ul>}
	</div>;
}
