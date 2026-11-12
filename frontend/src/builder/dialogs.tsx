import { Briefcase, FileJson, FileSpreadsheet, FileText, Link2, UploadCloud } from "lucide-react";
import { useState } from "react";
import { duplicateForm } from "./safety";
import { JOB_CONTEXT, download, entriesExportUrl, fileDownload, read, shareUrl, write, type EntryFilter } from "./api";
import { Alert, Btn, ChoiceCards, Modal, ShareLink, TextField } from "./kit";

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));
type Kind = "standalone" | "job";
const KIND_OPTIONS = [
	{value: "standalone" as const, title: "Shareable form", text: "Filled from one link. Your team can submit it as many times as needed.", icon: <Link2 className="size-[18px]" />},
	{value: "job" as const, title: "Job checklist", text: "Filled on a job's machines. Attach it to jobs with Form Rules.", icon: <Briefcase className="size-[18px]" />},
];

export function NewFormDialog({open, onClose, onCreated}: {open: boolean; onClose: () => void; onCreated: (name: string) => void}) {
	const [title, setTitle] = useState(""), [kind, setKind] = useState<Kind>("standalone");
	const [busy, setBusy] = useState(false), [error, setError] = useState("");
	async function create() {
		if (!title.trim()) {setError("Give the form a title."); return;}
		setBusy(true); setError("");
		try {onCreated(await write<string>("create_form", {title: title.trim(), context_doctype: kind === "job" ? JOB_CONTEXT : null}));}
		catch (e) {setError(message(e));} finally {setBusy(false);}
	}
	return <Modal open={open} title="Create a form" description="Start from a blank form. You can add fields, preview and publish next." onClose={onClose}
		footer={<><Btn onClick={onClose}>Cancel</Btn><Btn tone="primary" loading={busy} onClick={() => void create()}>Create form</Btn></>}>
		<form className="space-y-5" onSubmit={e => {e.preventDefault(); void create();}}>
			<TextField label="Form title" autoFocus placeholder="e.g. Site safety inspection" value={title} onChange={e => setTitle(e.target.value)} />
			<div><span className="mb-2 block text-sm font-medium text-slate-700">How is it filled?</span><ChoiceCards value={kind} options={KIND_OPTIONS} onChange={setKind} /></div>
			{error && <Alert>{error}</Alert>}
		</form>
	</Modal>;
}

type Parsed = {data: unknown; title: string; fields: number};
function parseImport(text: string): Parsed {
	const data = JSON.parse(text) as {form?: {title?: string}; title?: string; definition?: {sections?: {fields?: unknown[]}[]}; version?: {definition?: {sections?: {fields?: unknown[]}[]}}};
	const def = data.definition ?? data.version?.definition;
	return {data, title: data.form?.title ?? data.title ?? "Untitled form", fields: def?.sections?.reduce((n, s) => n + (s.fields?.length ?? 0), 0) ?? 0};
}

export function ImportDialog({open, onClose, onImported}: {open: boolean; onClose: () => void; onImported: (name: string) => void}) {
	const [file, setFile] = useState<{name: string; parsed: Parsed}>(), [error, setError] = useState(""), [busy, setBusy] = useState(false), [over, setOver] = useState(false);
	async function choose(f?: File) {
		setError(""); setFile(undefined); if (!f) return;
		try {setFile({name: f.name, parsed: parseImport(await f.text())});}
		catch {setError(`${f.name} is not a form export (JSON).`);}
	}
	async function run() {
		if (!file) return; setBusy(true); setError("");
		try {onImported(await write<string>("import_form", {data: file.parsed.data}));} catch (e) {setError(message(e));} finally {setBusy(false);}
	}
	function close() {setFile(undefined); setError(""); onClose();}
	return <Modal open={open} title="Import a form" description="Import a form design exported from DeployOps (.json). It's added as a new draft." onClose={close}
		footer={<><Btn onClick={close}>Cancel</Btn><Btn tone="primary" disabled={!file} loading={busy} onClick={() => void run()}>Import form</Btn></>}>
		<label onDragOver={e => {e.preventDefault(); setOver(true);}} onDragLeave={() => setOver(false)} onDrop={e => {e.preventDefault(); setOver(false); void choose(e.dataTransfer.files[0]);}}
			className={`flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center transition ${over ? "border-brand-500 bg-brand-50/50" : "border-slate-300 hover:border-slate-400 hover:bg-slate-50"}`}>
			<UploadCloud className="size-8 text-slate-400" aria-hidden />
			<span className="text-sm font-medium text-slate-800">Drop a .json file here, or <span className="text-brand-600">browse</span></span>
			<span className="text-xs text-slate-500">Form designs only. Entries can't be imported.</span>
			<input type="file" accept=".json,application/json" className="sr-only" onChange={e => {void choose(e.target.files?.[0]); e.target.value = "";}} />
		</label>
		{file && <div className="mt-4 flex items-center gap-3 rounded-lg bg-slate-50 p-3 ring-1 ring-slate-200"><FileJson className="size-5 text-slate-500" /><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{file.parsed.title}</p><p className="text-xs text-slate-500">{file.name} · {file.parsed.fields} fields</p></div></div>}
		{error && <div className="mt-4"><Alert>{error}</Alert></div>}
	</Modal>;
}

type Format = "xlsx" | "csv" | "json";
export function ExportDialog({open, form, title, hasEntries, initial = "xlsx", filter: preset, onClose}: {open: boolean; form: string; title: string; hasEntries: boolean; initial?: Format; filter?: EntryFilter; onClose: () => void}) {
	const [format, setFormat] = useState<Format>(hasEntries ? initial : "json");
	const [status, setStatus] = useState(preset?.status ?? ""), [from, setFrom] = useState(preset?.from_date ?? ""), [to, setTo] = useState(preset?.to_date ?? "");
	const [busy, setBusy] = useState(false), [error, setError] = useState(""), [done, setDone] = useState("");
	async function run() {
		setBusy(true); setError(""); setDone("");
		try {
			if (format === "json") {download(await read("export_form", {form}), title); setDone("Form design downloaded.");}
			else {fileDownload(entriesExportUrl(form, format, {status, from_date: from, to_date: to})); setDone("Your download has started.");}
		} catch (e) {setError(message(e));} finally {setBusy(false);}
	}
	const options: {value: Format; title: string; text: string; icon: React.ReactNode; disabled?: boolean}[] = [
		{value: "xlsx", title: "Excel", text: "Entries, one row each. Best for reading and filtering.", icon: <FileSpreadsheet className="size-[18px]" />, disabled: !hasEntries},
		{value: "csv", title: "CSV", text: "Entries as plain text, for other tools.", icon: <FileText className="size-[18px]" />, disabled: !hasEntries},
		{value: "json", title: "Form design", text: "Questions and rules (JSON) to import elsewhere. No answers.", icon: <FileJson className="size-[18px]" />},
	];
	return <Modal open={open} title={`Export “${title}”`} description="Choose what to download." size="lg" onClose={onClose}
		footer={<><Btn onClick={onClose}>Close</Btn><Btn tone="primary" loading={busy} onClick={() => void run()}>Download</Btn></>}>
		<div className="space-y-5">
			<div><span className="mb-2 block text-sm font-medium text-slate-700">Format</span><ChoiceCards columns={3} value={format} options={options} onChange={setFormat} /></div>
			{!hasEntries && <Alert kind="info">This form has no entries yet, so only the design can be exported.</Alert>}
			{format !== "json" && <fieldset className="grid gap-4 rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200 sm:grid-cols-3">
				<legend className="sr-only">Filter entries</legend>
				<label className="block"><span className="mb-1.5 block text-sm font-medium text-slate-700">Status</span><select className="bld-input" value={status} onChange={e => setStatus(e.target.value)}><option value="">All entries</option><option value="Submitted">Submitted only</option><option value="Draft">Drafts only</option><option value="Cancelled">Cancelled only</option></select></label>
				<TextField label="Started from" type="date" value={from} max={to || undefined} onChange={e => setFrom(e.target.value)} />
				<TextField label="Started to" type="date" value={to} min={from || undefined} onChange={e => setTo(e.target.value)} />
			</fieldset>}
			{error && <Alert>{error}</Alert>}{done && <Alert kind="success">{done}</Alert>}
		</div>
	</Modal>;
}

export function ShareDialog({open, form, title, onClose}: {open: boolean; form: string; title: string; onClose: () => void}) {
	const url = shareUrl(form);
	return <Modal open={open} title="Share form" description="Anyone on your team with a DeployOps login can open this link. Each visit starts a new entry." onClose={onClose} footer={<><a className="mr-auto text-sm font-medium text-brand-600 hover:underline" href={url} target="_blank" rel="noreferrer">Open form ↗</a><Btn onClick={onClose}>Done</Btn></>}>
		<ShareLink url={url} title={title} />
	</Modal>;
}

export function DuplicateDialog({open, form, title, onClose, onDone}: {open: boolean; form: string; title: string; onClose: () => void; onDone: (name: string) => void}) {
	const [name, setName] = useState(`${title} (copy)`), [kind, setKind] = useState<Kind>("standalone"), [busy, setBusy] = useState(false), [error, setError] = useState("");
	async function run() {
		setBusy(true); setError("");
		try {
			const data = await read<{form?: Record<string, unknown>}>("export_form", {form});
			const copy = {...data, form: {...data.form, title: name.trim() || `${title} (copy)`, context_doctype: kind === "job" ? JOB_CONTEXT : null}};
			onDone(await duplicateForm(copy, args => write<string>("import_form", args)) as string);
		} catch (e) {setError(message(e));} finally {setBusy(false);}
	}
	return <Modal open={open} title="Duplicate form" description="Makes a new draft with the same questions. Entries aren't copied." onClose={onClose}
		footer={<><Btn onClick={onClose}>Cancel</Btn><Btn tone="primary" loading={busy} onClick={() => void run()}>Duplicate</Btn></>}>
		<div className="space-y-5"><TextField label="New title" autoFocus value={name} onChange={e => setName(e.target.value)} />
			<div><span className="mb-2 block text-sm font-medium text-slate-700">How is the copy filled?</span><ChoiceCards value={kind} options={KIND_OPTIONS} onChange={setKind} /></div>
			{kind === "standalone" && <p className="text-xs text-slate-500">Job values (customer, serial…) aren't available in a shareable form; publishing will point out any field that uses them.</p>}
			{error && <Alert>{error}</Alert>}</div>
	</Modal>;
}
