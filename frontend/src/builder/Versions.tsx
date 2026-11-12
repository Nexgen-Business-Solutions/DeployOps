import { ArrowLeft, Eye, GitCompare, History, RotateCcw } from "lucide-react";
import { useState } from "react";
import { beforeRestore } from "./safety";
import { read, write, type Catalog, type FormRecord } from "./api";
import { Preview } from "./Preview";
import { ChangeSummary, labelIndex, type PublishCheck } from "./Publish";
import type { Definition } from "../forms/types";
import { Alert, Btn, Confirm, Modal, formatDate } from "./kit";

export function Versions({record, catalog, flush, token, restore, onClose}: {flush: () => Promise<void>; token: () => string; record: FormRecord; catalog: Catalog; restore: () => Promise<unknown>; onClose: () => void}) {
	const [view, setView] = useState<{no: number; definition: Definition}>(), [summary, setSummary] = useState<PublishCheck["summary"]>(), [labels, setLabels] = useState<Record<string, string>>({});
	const [message, setMessage] = useState(""), [busy, setBusy] = useState(false), [restoring, setRestoring] = useState<FormRecord["versions"][number]>();
	const [a, setA] = useState(record.versions[1]?.name ?? record.versions[0]?.name ?? ""), [b, setB] = useState(record.versions[0]?.name ?? "");
	async function run(action: () => Promise<void>) {setBusy(true); setMessage(""); try {await action();} catch(e) {setMessage(e instanceof Error ? e.message : String(e));} finally {setBusy(false);}}
	const definitionOf = async (version: string) => {const v = await read<{definition: string | Definition}>("get_version", {version}); return typeof v.definition === "string" ? JSON.parse(v.definition) as Definition : v.definition;};
	return <Modal open size={view ? "xl" : "lg"} title={view ? `Version ${view.no}` : "Version history"} description={view ? "Read only" : `${record.versions.length} published version${record.versions.length === 1 ? "" : "s"}`} onClose={onClose}
		footer={view ? <Btn icon={<ArrowLeft className="size-4" />} onClick={() => setView(undefined)}>Back to versions</Btn> : <Btn onClick={onClose}>Close</Btn>}>
		{message && <div className="mb-4"><Alert>{message}</Alert></div>}
		{view ? <Preview definition={view.definition} catalog={catalog} form={record.name} readonly /> : record.versions.length === 0 ? <div className="py-12 text-center text-sm text-slate-500"><History className="mx-auto mb-3 size-8 text-slate-300" />No versions yet. Publish the form to create version 1.</div> : <div className="space-y-6">
			<ol className="divide-y divide-slate-100 rounded-xl ring-1 ring-slate-200">{record.versions.map((v, i) => <li key={v.name} className="flex items-center gap-4 px-4 py-3">
				<span className="grid size-9 shrink-0 place-items-center rounded-full bg-slate-100 text-sm font-semibold text-slate-700">v{v.version_no}</span>
				<div className="min-w-0 flex-1"><p className="flex items-center gap-2 text-sm font-medium text-slate-900">{v.change_note || <span className="font-normal italic text-slate-400">No change note</span>}{i === 0 && <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700 ring-1 ring-inset ring-emerald-200">Current</span>}</p><p className="text-xs text-slate-500">{formatDate(v.published_on, true)} · {v.published_by}</p></div>
				<Btn size="sm" tone="ghost" disabled={busy} icon={<Eye className="size-3.5" />} onClick={() => void run(async () => setView({no: v.version_no, definition: await definitionOf(v.name)}))}>View</Btn>
				<Btn size="sm" disabled={busy} icon={<RotateCcw className="size-3.5" />} onClick={() => setRestoring(v)}>Restore</Btn>
			</li>)}</ol>
			{record.versions.length > 1 && <section className="rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200">
				<h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900"><GitCompare className="size-4" />Compare versions</h3>
				<div className="flex flex-wrap items-end gap-3">
					<label className="block"><span className="mb-1 block text-xs font-medium text-slate-600">From</span><select className="bld-input w-28" value={a} onChange={e => setA(e.target.value)}>{record.versions.map(v => <option key={v.name} value={v.name}>v{v.version_no}</option>)}</select></label>
					<label className="block"><span className="mb-1 block text-xs font-medium text-slate-600">To</span><select className="bld-input w-28" value={b} onChange={e => setB(e.target.value)}>{record.versions.map(v => <option key={v.name} value={v.name}>v{v.version_no}</option>)}</select></label>
					<Btn tone="primary" loading={busy} disabled={!a || !b || a === b} onClick={() => void run(async () => {const [da, db, s] = await Promise.all([definitionOf(a), definitionOf(b), read<PublishCheck["summary"]>("compare_versions", {a, b})]); setLabels(labelIndex(da, db)); setSummary(s);})}>Compare</Btn>
				</div>
				{summary && <div className="mt-4"><ChangeSummary summary={summary} labels={labels} /></div>}
			</section>}
		</div>}
		<Confirm open={!!restoring} title={`Restore v${restoring?.version_no}?`} confirmLabel="Restore as draft" busy={busy} onClose={() => setRestoring(undefined)}
			message="The current draft is replaced with this version's questions. Published versions and entries aren't changed. You can publish the restored draft as a new version."
			onConfirm={() => {const v = restoring!; void run(async () => {await beforeRestore(flush, token, modified => write("restore_as_draft", {version: v.name, modified}), restore); setRestoring(undefined); onClose();});}} />
	</Modal>;
}
