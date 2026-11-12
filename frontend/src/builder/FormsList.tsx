import { Archive, Briefcase, Copy, Download, FilePlus2, FileUp, Inbox, Link2, MoreHorizontal, Pencil, Search, Share2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { TopBar } from "../components/ui";
import { useApi } from "../lib/useApi";
import { useSession } from "../lib/session";
import { isDesigner, isShareable, write, type ListedForm } from "./api";
import { DuplicateDialog, ExportDialog, ImportDialog, NewFormDialog, ShareDialog } from "./dialogs";
import { Alert, Badge, Btn, Confirm, IconBtn, Spinner, formatDate } from "./kit";

type Filter = "All" | "Draft" | "Published" | "Archived";
type Dialog = {kind: "share" | "export" | "duplicate" | "archive"; form: ListedForm} | {kind: "new" | "import"};

export default function FormsList() {
	const me = useSession(), navigate = useNavigate();
	const {data: forms, reload, error, loading} = useApi<ListedForm[]>("forms_core.api.list_forms");
	const {data: counts} = useApi<Record<string, number>>("deployops.api.forms.form_rule_counts");
	const [query, setQuery] = useState(""), [filter, setFilter] = useState<Filter>("All");
	const [dialog, setDialog] = useState<Dialog>(), [busy, setBusy] = useState(false), [notice, setNotice] = useState<{kind: "error" | "success"; text: string}>();
	const shown = useMemo(() => (forms ?? []).filter(f => (filter === "All" ? f.status !== "Archived" : f.status === filter) && f.title.toLowerCase().includes(query.trim().toLowerCase())), [forms, filter, query]);
	const tally = (s: Filter) => (forms ?? []).filter(f => (s === "All" ? f.status !== "Archived" : f.status === s)).length;
	if (!isDesigner(me.roles, me.user)) return <><TopBar title="Forms" back="/" /><div className="p-8"><Alert>Only form designers can open the builder.</Alert></div></>;
	const close = () => setDialog(undefined);
	const open = (name: string) => navigate(`/builder/${encodeURIComponent(name)}`);
	async function archive(form: ListedForm) {
		setBusy(true);
		try {await write("archive", {form: form.name}); await reload(); setNotice({kind: "success", text: `“${form.title}” was archived. It no longer takes new entries.`}); close();}
		catch (e) {setNotice({kind: "error", text: e instanceof Error ? e.message : String(e)}); close();}
		finally {setBusy(false);}
	}
	return <>
		<TopBar title="Forms" subtitle="Design, publish and share forms" right={<>
			<Btn className="builder-edit" icon={<FileUp className="size-4" />} onClick={() => setDialog({kind: "import"})}>Import</Btn>
			<Btn className="builder-edit" tone="primary" icon={<FilePlus2 className="size-4" />} onClick={() => setDialog({kind: "new"})}>New form</Btn>
		</>} />
		<main className="mx-auto max-w-7xl space-y-4 px-4 py-6 sm:px-6 lg:px-8">
			<p className="builder-small rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900 ring-1 ring-amber-200">Open the builder on a larger screen to create or edit forms.</p>
			{notice && <Alert kind={notice.kind}>{notice.text}</Alert>}
			{error && <Alert>{error.message}</Alert>}
			<div className="flex flex-wrap items-center gap-3">
				<div role="tablist" className="flex rounded-lg bg-slate-100 p-1">{(["All", "Draft", "Published", "Archived"] as Filter[]).map(s => <button key={s} role="tab" aria-selected={filter === s} onClick={() => setFilter(s)} className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${filter === s ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"}`}>{s === "All" ? "Active" : s}<span className="ml-1.5 text-xs text-slate-400">{forms ? tally(s) : ""}</span></button>)}</div>
				<label className="relative ml-auto w-full max-w-xs"><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" /><input className="bld-input pl-9" type="search" placeholder="Search forms" value={query} onChange={e => setQuery(e.target.value)} /></label>
			</div>
			<div className="overflow-visible rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
				{loading && !forms ? <Spinner label="Loading forms" /> : shown.length === 0 ? <EmptyState searching={!!query || filter !== "All"} onNew={() => setDialog({kind: "new"})} /> :
				<table className="w-full text-left text-sm">
					<thead className="border-b border-slate-200 bg-slate-50/80 text-xs font-medium uppercase tracking-wide text-slate-500"><tr>
						<th className="py-3 pl-5 pr-3">Form</th><th className="px-3 py-3">Status</th><th className="px-3 py-3">Version</th><th className="px-3 py-3">Entries</th><th className="px-3 py-3">Last published</th><th className="py-3 pl-3 pr-5 text-right"><span className="sr-only">Actions</span></th>
					</tr></thead>
					<tbody className="divide-y divide-slate-100">{shown.map(form => <tr key={form.name} className="group hover:bg-slate-50/70">
						<td className="py-3 pl-5 pr-3"><Link to={`/builder/${encodeURIComponent(form.name)}`} className="flex items-center gap-3">
							<span className={`grid size-9 shrink-0 place-items-center rounded-lg ${form.context_doctype ? "bg-violet-50 text-violet-600" : "bg-blue-50 text-blue-600"}`}>{form.context_doctype ? <Briefcase className="size-4" /> : <Link2 className="size-4" />}</span>
							<span className="min-w-0"><span className="block truncate font-medium text-slate-900 group-hover:text-brand-600">{form.title}</span><span className="block text-xs text-slate-500">{form.context_doctype ? `Job checklist · ${counts?.[form.name] ?? 0} rule${counts?.[form.name] === 1 ? "" : "s"}` : "Shareable form"} · edited {formatDate(form.modified)}</span></span>
						</Link></td>
						<td className="px-3 py-3"><Badge kind={form.status} /></td>
						<td className="px-3 py-3 tabular-nums text-slate-600">{form.version_no ? `v${form.version_no}` : "—"}</td>
						<td className="px-3 py-3 tabular-nums text-slate-600">{form.entries > 0 ? <Link className="hover:text-brand-600 hover:underline" to={`/builder/${encodeURIComponent(form.name)}?tab=entries`}>{form.entries}</Link> : "0"}</td>
						<td className="px-3 py-3 text-slate-600">{formatDate(form.published_on)}</td>
						<td className="py-2 pl-3 pr-5"><div className="flex items-center justify-end gap-1">
							{isShareable(form) && <Btn size="sm" icon={<Share2 className="size-3.5" />} onClick={() => setDialog({kind: "share", form})}>Share</Btn>}
							<RowMenu items={[
								{label: "Edit", icon: <Pencil className="size-4" />, run: () => open(form.name), edit: true},
								{label: "Entries", icon: <Inbox className="size-4" />, run: () => navigate(`/builder/${encodeURIComponent(form.name)}?tab=entries`)},
								{label: "Export…", icon: <Download className="size-4" />, run: () => setDialog({kind: "export", form})},
								{label: "Duplicate…", icon: <Copy className="size-4" />, run: () => setDialog({kind: "duplicate", form}), edit: true},
								...(form.status !== "Archived" ? [{label: "Archive…", icon: <Archive className="size-4" />, run: () => setDialog({kind: "archive", form}), danger: true, edit: true}] : []),
							]} />
						</div></td>
					</tr>)}</tbody>
				</table>}
			</div>
		</main>
		<NewFormDialog open={dialog?.kind === "new"} onClose={close} onCreated={open} />
		<ImportDialog open={dialog?.kind === "import"} onClose={close} onImported={open} />
		{dialog && "form" in dialog && <>
			<ShareDialog open={dialog.kind === "share"} form={dialog.form.name} title={dialog.form.title} onClose={close} />
			{dialog.kind === "export" && <ExportDialog open form={dialog.form.name} title={dialog.form.title} hasEntries={dialog.form.entries > 0} onClose={close} />}
			{dialog.kind === "duplicate" && <DuplicateDialog open form={dialog.form.name} title={dialog.form.title} onClose={close} onDone={open} />}
			<Confirm open={dialog.kind === "archive"} danger busy={busy} title="Archive form?" confirmLabel="Archive form" onClose={close} onConfirm={() => void archive(dialog.form)}
				message={<>“{dialog.form.title}” will stop taking new entries{dialog.form.context_doctype ? " and won't be added to new jobs" : " and its share link will stop working"}. Existing entries are kept and can still be exported.</>} />
		</>}
	</>;
}

function EmptyState({searching, onNew}: {searching: boolean; onNew: () => void}) {
	return <div className="flex flex-col items-center px-6 py-16 text-center">
		<span className="grid size-12 place-items-center rounded-xl bg-slate-100 text-slate-500"><FilePlus2 className="size-6" /></span>
		<p className="mt-4 font-semibold text-slate-900">{searching ? "No forms match" : "No forms yet"}</p>
		<p className="mt-1 max-w-sm text-sm text-slate-500">{searching ? "Try another search or status." : "Create a form, add questions, then publish it and share the link with your team."}</p>
		{!searching && <Btn className="builder-edit mt-5" tone="primary" icon={<FilePlus2 className="size-4" />} onClick={onNew}>New form</Btn>}
	</div>;
}

type MenuItem = {label: string; icon: React.ReactNode; run: () => void; danger?: boolean; edit?: boolean};
function RowMenu({items}: {items: MenuItem[]}) {
	const [open, setOpen] = useState(false), ref = useRef<HTMLDivElement>(null);
	useEffect(() => {
		if (!open) return;
		const away = (e: MouseEvent) => {if (!ref.current?.contains(e.target as Node)) setOpen(false);};
		const key = (e: KeyboardEvent) => {if (e.key === "Escape") setOpen(false);};
		document.addEventListener("mousedown", away); document.addEventListener("keydown", key);
		return () => {document.removeEventListener("mousedown", away); document.removeEventListener("keydown", key);};
	}, [open]);
	return <div ref={ref} className="relative">
		<IconBtn label="More actions" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(o => !o)}><MoreHorizontal className="size-4" /></IconBtn>
		{open && <div role="menu" className="absolute right-0 top-9 z-30 w-44 overflow-hidden rounded-xl bg-white py-1 shadow-lg ring-1 ring-slate-200">{items.map(item => <button key={item.label} role="menuitem" type="button" onClick={() => {setOpen(false); item.run();}}
			className={`flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm ${item.edit ? "builder-edit" : ""} ${item.danger ? "text-red-600 hover:bg-red-50" : "text-slate-700 hover:bg-slate-50"}`}>{item.icon}{item.label}</button>)}</div>}
	</div>;
}
