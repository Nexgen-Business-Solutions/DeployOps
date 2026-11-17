import { AlertCircle, CheckCircle2, ChevronRight, Minus, PartyPopper, Pencil, Plus } from "lucide-react";
import { useState } from "react";
import type { Definition, FormError } from "../forms/types";
import { ApiError } from "../lib/api";
import { publishChecked } from "./safety";
import { read, write, type FormRecord } from "./api";
import { Alert, Btn, Modal } from "./kit";
import { SharePanel } from "./ShareSettings";

export type PublishCheck = {modified: string; errors: FormError[]; summary: {added: string[]; removed: string[]; changed: string[]}; drafts_on_older: Record<string, number>};

/** id -> label for every field and table column of the given definitions (later ones win). */
export function labelIndex(...defs: (Definition | undefined)[]): Record<string, string> {
	const out: Record<string, string> = {};
	for (const def of defs) for (const s of def?.sections ?? []) {
		out[s.id] = s.title ? `Step: ${s.title}` : "Step";
		for (const f of s.fields) {
			out[f.id] = f.label || f.key;
			for (const c of (f.config?.columns ?? []) as {id: string; label: string}[]) out[c.id] = `${f.label} › ${c.label}`;
		}
	}
	return out;
}

export function ChangeSummary({summary, labels = {}}: {summary: PublishCheck["summary"]; labels?: Record<string, string>}) {
	const rows = [
		{key: "added" as const, title: "Added", icon: <Plus className="size-3.5" />, style: "bg-emerald-50 text-emerald-700"},
		{key: "changed" as const, title: "Changed", icon: <Pencil className="size-3.5" />, style: "bg-blue-50 text-blue-700"},
		{key: "removed" as const, title: "Removed", icon: <Minus className="size-3.5" />, style: "bg-red-50 text-red-700"},
	];
	const total = rows.reduce((n, r) => n + summary[r.key].length, 0);
	if (!total) return <p className="text-sm text-slate-500">No changes to the questions since the last version.</p>;
	return <div className="grid gap-3 sm:grid-cols-3">{rows.map(r => <div key={r.key} className="rounded-lg ring-1 ring-slate-200">
		<p className="flex items-center gap-2 border-b border-slate-100 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500"><span className={`grid size-5 place-items-center rounded ${r.style}`}>{r.icon}</span>{r.title}<span className="ml-auto tabular-nums">{summary[r.key].length}</span></p>
		<ul className="max-h-40 space-y-1 overflow-y-auto px-3 py-2 text-[13px] text-slate-700">{summary[r.key].length ? summary[r.key].map(id => <li key={id} className="truncate">{labels[id] ?? id}</li>) : <li className="text-slate-400">None</li>}</ul>
	</div>)}</div>;
}

export function Publish({record, check, definition, flush, onSelect, onPublished, onClose, onChooseJobs}: {onChooseJobs?: () => void; flush: () => Promise<void>; record: FormRecord; check: PublishCheck; definition: Definition; onSelect: (field: string, message: string) => void; onPublished: () => Promise<unknown>; onClose: () => void}) {
	const [note, setNote] = useState(""), [errors, setErrors] = useState(check.errors), [message, setMessage] = useState(""), [busy, setBusy] = useState(false);
	const [published, setPublished] = useState(false);
	const labels = labelIndex(definition);
	const nextVersion = (record.versions[0]?.version_no ?? 0) + 1;
	const standalone = !record.context_doctype;
	function publish() {
		setBusy(true); setMessage("");
		void publishChecked(flush, async () => {
			const next = await read<PublishCheck>("publish_preview", {form: record.name});
			if (next.modified !== check.modified) throw new Error("The draft changed while this was open. Close and open Publish again to review the latest changes.");
			return next;
		}, modified => write("publish", {form: record.name, change_note: note, modified}))
			.then(() => setPublished(true))
			.catch((e: unknown) => {if (e instanceof ApiError && e.formErrors) setErrors(e.formErrors); setMessage(e instanceof Error ? e.message : String(e));})
			.finally(() => setBusy(false));
	}
	function finish() {void onPublished(); onClose();}
	if (published) return <Modal open size="md" title={<span className="flex items-center gap-2"><PartyPopper className="size-5 text-emerald-600" />Version {nextVersion} is live</span>} onClose={finish} footer={<Btn tone={standalone ? "primary" : "secondary"} onClick={finish}>Done</Btn>}>
		{standalone ? <div className="space-y-4">
			<SharePanel form={record.name} title={record.title} />
		</div> : <div className="space-y-4 text-sm text-slate-600">
			<p>Jobs that already use this checklist get this version for machines that haven't started it yet. To choose which job types and equipment get it, add a rule.</p>
			<Btn tone="primary" icon={<ChevronRight className="size-4" />} onClick={() => {onChooseJobs?.(); finish();}}>Choose which jobs get it</Btn>
		</div>}
	</Modal>;
	return <Modal open size="lg" title={`Publish version ${nextVersion}`} description={errors.length ? "Fix these before publishing." : "Review the changes, then publish."} onClose={onClose}
		footer={<><Btn onClick={onClose}>Cancel</Btn><Btn tone="primary" loading={busy} disabled={errors.length > 0} onClick={publish}>Publish v{nextVersion}</Btn></>}>
		<div className="space-y-5">
			{errors.length > 0 ? <div className="rounded-xl ring-1 ring-red-200">
				<p className="flex items-center gap-2 border-b border-red-100 bg-red-50 px-4 py-2.5 text-sm font-semibold text-red-800"><AlertCircle className="size-4" />{errors.length} problem{errors.length === 1 ? "" : "s"} to fix</p>
				<ul className="divide-y divide-red-50">{errors.map((error, i) => <li key={i}><button type="button" onClick={() => onSelect(error.field ?? "", error.message)} className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm hover:bg-red-50/50">
					<span className="min-w-0 flex-1"><span className="block font-medium text-slate-900">{error.field ? labels[error.field] ?? error.field : "Form"}{error.row ? ` · row ${error.row}` : ""}</span><span className="block text-slate-600">{error.message}</span></span>
					{error.field && <span className="shrink-0 text-xs font-medium text-brand-600">Go to field</span>}
				</button></li>)}</ul>
			</div> : <p className="flex items-center gap-2 text-sm font-medium text-emerald-700"><CheckCircle2 className="size-4" />All checks passed</p>}
			<div><h3 className="mb-2 text-sm font-semibold text-slate-900">What changes</h3><ChangeSummary summary={check.summary} labels={labels} /></div>
			{Object.entries(check.drafts_on_older).map(([version, count]) => <Alert key={version} kind="warning">{count} draft{count === 1 ? " is" : "s are"} on v{record.versions.find(v => v.name === version)?.version_no ?? version} and will stay there unless moved up.</Alert>)}
			<label className="block"><span className="mb-1.5 block text-sm font-medium text-slate-700">Change note <span className="font-normal text-slate-400">(optional)</span></span><textarea className="bld-input min-h-20" placeholder="What changed and why" value={note} onChange={e => setNote(e.target.value)} /></label>
			{message && <Alert>{message}</Alert>}
		</div>
	</Modal>;
}
