import { FileDown, ChevronLeft, ChevronRight, Download, ExternalLink, Inbox, RefreshCw, Share2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { useApi } from "../lib/useApi";
import type { EntryList } from "./api";
import { ExportDialog } from "./dialogs";
import { Alert, Badge, Btn, Spinner, TextField, formatDate } from "./kit";

const PAGE = 25;
const STATUSES = ["", "Submitted", "Draft", "Cancelled"];

export function Entries({form, title, jobForm, canShare, onShare}: {form: string; title: string; jobForm: boolean; canShare: boolean; onShare: () => void}) {
	const [status, setStatus] = useState(""), [from, setFrom] = useState(""), [to, setTo] = useState(""), [page, setPage] = useState(0), [exporting, setExporting] = useState(false);
	const {data, error, loading, reload} = useApi<EntryList>("forms_core.api.list_entries", {form, status: status || undefined, from_date: from || undefined, to_date: to || undefined, start: page * PAGE, limit: PAGE});
	const all = data ? Object.values(data.counts).reduce((a, b) => a + b, 0) : 0;
	const pages = data ? Math.max(1, Math.ceil(data.total / PAGE)) : 1;
	const reset = (fn: () => void) => {fn(); setPage(0);};
	return <div className="mx-auto max-w-6xl space-y-4 px-8 py-6">
		<div className="flex flex-wrap items-end gap-3">
			<div><h2 className="text-lg font-semibold text-slate-900">Entries</h2><p className="text-sm text-slate-500">Every time this form is filled{jobForm ? " on a job" : ""}, it's recorded here.</p></div>
			<span className="flex-1" />
			<Btn tone="ghost" icon={<RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />} onClick={() => void reload()}>Refresh</Btn>
			<Btn tone="primary" icon={<Download className="size-4" />} onClick={() => setExporting(true)}>Export</Btn>
		</div>
		<div className="flex flex-wrap items-end gap-3 rounded-xl bg-white p-3 shadow-sm ring-1 ring-slate-200">
			<div role="tablist" className="flex rounded-lg bg-slate-100 p-1">{STATUSES.map(s => <button key={s || "all"} role="tab" aria-selected={status === s} onClick={() => reset(() => setStatus(s))}
				className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${status === s ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"}`}>{s || "All"}<span className="ml-1.5 text-xs text-slate-400">{data ? (s ? data.counts[s] ?? 0 : all) : ""}</span></button>)}</div>
			<span className="flex-1" />
			<div className="w-40"><TextField label="Started from" type="date" value={from} max={to || undefined} onChange={e => reset(() => setFrom(e.target.value))} /></div>
			<div className="w-40"><TextField label="Started to" type="date" value={to} min={from || undefined} onChange={e => reset(() => setTo(e.target.value))} /></div>
			{(from || to) && <Btn tone="ghost" onClick={() => reset(() => {setFrom(""); setTo("");})}>Clear dates</Btn>}
		</div>
		{error && <Alert>{error.message}</Alert>}
		<div className="overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
			{!data ? <Spinner label="Loading entries" /> : data.rows.length === 0 ? <div className="flex flex-col items-center px-6 py-16 text-center">
				<span className="grid size-12 place-items-center rounded-xl bg-slate-100 text-slate-500"><Inbox className="size-6" /></span>
				<p className="mt-4 font-semibold text-slate-900">{all ? "No entries match these filters" : "No entries yet"}</p>
				<p className="mt-1 max-w-sm text-sm text-slate-500">{all ? "Try another status or date range." : jobForm ? "Entries appear when technicians fill this checklist on a job." : "Share the form's link with your team. Each submission appears here."}</p>
				{!all && canShare && <Btn className="mt-5" tone="primary" icon={<Share2 className="size-4" />} onClick={onShare}>Share form</Btn>}
			</div> : <table className="w-full text-left text-sm">
				<thead className="border-b border-slate-200 bg-slate-50/80 text-xs font-medium uppercase tracking-wide text-slate-500"><tr>
					<th className="py-3 pl-5 pr-3">Entry</th><th className="px-3 py-3">Status</th>{jobForm && <th className="px-3 py-3">Job</th>}<th className="px-3 py-3">Started by</th><th className="px-3 py-3">Started</th><th className="px-3 py-3">Submitted</th><th className="px-3 py-3">Version</th><th className="py-3 pl-3 pr-5" />
				</tr></thead>
				<tbody className="divide-y divide-slate-100">{data.rows.map(r => <tr key={r.name} className="hover:bg-slate-50/70">
					<td className="py-3 pl-5 pr-3 font-mono text-[13px] text-slate-700">{r.name}</td>
					<td className="px-3 py-3"><Badge kind={r.status} /></td>
					{jobForm && <td className="px-3 py-3 text-slate-600">{r.context ? <Link className="hover:text-brand-600 hover:underline" to={`/job/${encodeURIComponent(r.context)}`}>{r.context}</Link> : "—"}</td>}
					<td className="px-3 py-3 text-slate-700">{r.started_by}</td>
					<td className="px-3 py-3 text-slate-600">{formatDate(r.created, true)}</td>
					<td className="px-3 py-3 text-slate-600">{r.submitted_on ? <>{formatDate(r.submitted_on, true)}{r.submitted_by && r.submitted_by !== r.started_by && <span className="block text-xs text-slate-400">by {r.submitted_by}</span>}</> : "—"}</td>
					<td className="px-3 py-3 tabular-nums text-slate-600">{r.version_no ? `v${r.version_no}` : "—"}</td>
					<td className="py-3 pl-3 pr-5 text-right">{r.status === "Submitted" && <a href={`/api/method/deployops.api.forms.submission_pdf?name=${encodeURIComponent(r.name)}&audience=internal`} className="mr-4 inline-flex items-center gap-1 text-[13px] font-medium text-slate-600 hover:text-brand-600 hover:underline"><FileDown className="size-3.5" />PDF</a>}<Link to={`/s/${encodeURIComponent(r.name)}`} className="inline-flex items-center gap-1 text-[13px] font-medium text-brand-600 hover:underline">Open<ExternalLink className="size-3.5" /></Link></td>
				</tr>)}</tbody>
			</table>}
			{data && data.total > PAGE && <footer className="flex items-center gap-3 border-t border-slate-200 px-5 py-3 text-sm text-slate-600">
				<span>{page * PAGE + 1}–{Math.min(data.total, (page + 1) * PAGE)} of {data.total}</span><span className="flex-1" />
				<Btn size="sm" disabled={page === 0} icon={<ChevronLeft className="size-4" />} onClick={() => setPage(p => p - 1)}>Previous</Btn>
				<Btn size="sm" disabled={page + 1 >= pages} onClick={() => setPage(p => p + 1)}>Next<ChevronRight className="size-4" /></Btn>
			</footer>}
		</div>
		{exporting && <ExportDialog open form={form} title={title} hasEntries={all > 0} filter={{status, from_date: from, to_date: to}} onClose={() => setExporting(false)} />}
	</div>;
}
