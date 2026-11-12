import { ArrowLeft, Briefcase, Check, CloudOff, Eye, History, Link2, Loader2, MousePointerClick, Redo2, Rocket, Share2, Undo2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useBlocker, useParams, useSearchParams } from "react-router";
import { useApi } from "../lib/useApi";
import { useSession } from "../lib/session";
import type { Definition, ColumnDef } from "../forms/types";
import { getPlugin } from "../forms/fields";
import { read, write, isDesigner, isShareable, type Catalog, type FormRecord } from "./api";
import { History as EditHistory, dependencies, type Action, type BuilderDefinition } from "./state";
import { errorTarget, saveBeforeNavigation } from "./safety";
import { Autosave } from "./autosave";
import { newId } from "./ids";
import { SettingsPanel } from "./SettingsPanel";
import { Canvas } from "./Canvas";
import { Documents } from "./Documents";
import { PreviewScreen } from "./Preview";
import { Publish, type PublishCheck } from "./Publish";
import { Versions } from "./Versions";
import { Entries } from "./Entries";
import { Rules } from "./Rules";
import { ShareDialog } from "./dialogs";
import { fieldLabel } from "./fieldIcons";
import { Alert, Badge, Btn, Confirm, IconBtn, Spinner, TextField } from "./kit";

export default function Builder() {
	const {form = ""} = useParams(); const me = useSession();
	const {data, error, reload} = useApi<FormRecord>("forms_core.api.get_form", {form});
	const {data: catalog} = useApi<Catalog>("forms_core.api.designer_catalog", {context_doctype: data?.context_doctype});
	if (!isDesigner(me.roles, me.user)) return <div className="p-8"><Alert>Only form designers can open the builder.</Alert></div>;
	return <>
		<div className="builder-small p-6"><Alert kind="info">Open the builder on a larger screen (1024px or wider) to edit this form.</Alert></div>
		{error ? <div className="p-8"><Alert>{error.message}</Alert></div> : data && catalog ? <Editor key={`${form}:${data.modified}`} record={data} catalog={catalog} reload={reload} /> : <div className="builder-screen"><Spinner label="Loading builder" /></div>}
	</>;
}

type Tab = "build" | "entries" | "documents" | "appearance" | "rules";
type Panel = "" | "preview" | "publish" | "versions" | "share";

export function Editor({record, catalog, reload}: {record: FormRecord; catalog: Catalog; reload: () => Promise<unknown>}) {
	const [history] = useState(() => new EditHistory({...parseDefinition(record.draft_definition), title: record.title, appearance: {subtitle: record.subtitle ?? "", icon: record.icon ?? "", color: record.color ?? ""}}));
	const [def, setDef] = useState(history.current); const [, refresh] = useState(0);
	const [selected, select] = useState(def.sections[0]?.id ?? "");
	const [params, setParams] = useSearchParams();
	const tab = (params.get("tab") as Tab) || "build";
	const setTab = (t: Tab) => setParams(t === "build" ? {} : {tab: t}, {replace: true});
	const [message, setMessage] = useState("");
	const [panel, setPanel] = useState<Panel>(""); const [check, setCheck] = useState<PublishCheck>(); const [busy, setBusy] = useState(false);
	const [fieldError, setFieldError] = useState<{id: string; message: string}>();
	const [deleting, setDeleting] = useState<{id: string; section: boolean; affected: string[]}>();
	const [reloading, setReloading] = useState(false);
	const jobForm = !!record.context_doctype;
	async function openPanel(target: Panel) {setBusy(true); setMessage(""); try {await autosave.flush(); if (target === "publish") setCheck(await read<PublishCheck>("publish_preview", {form: record.name})); setPanel(target);} catch(e) {setMessage(e instanceof Error ? e.message : String(e));} finally {setBusy(false);}}
	const [autosave] = useState(() => new Autosave<BuilderDefinition>(record.modified, async (value, modified) => {
		const {title, appearance, ...definition} = value;
		return write<{modified: string}>("save_draft", {form: record.name, definition, modified, title, appearance});
	}, () => refresh(n => n + 1)));
	useEffect(() => {autosave.activate(); return () => autosave.dispose();}, [autosave]);
	const blocker = useBlocker(({currentLocation, nextLocation}) => autosave.state !== "saved" && currentLocation.pathname !== nextLocation.pathname);
	useEffect(() => {
		if (blocker.state !== "blocked") return;
		let active = true;
		void saveBeforeNavigation(() => autosave.flush(), () => {if (active) blocker.proceed();}, message => {if (active) {setMessage(message); blocker.reset();}});
		return () => {active = false;};
	}, [blocker, autosave]);
	useEffect(() => {
		const listener = (event: Event) => {
			if (autosave.state === "saved") return;
			event.preventDefault();
			void saveBeforeNavigation(() => autosave.flush(), (event as CustomEvent<{resume: () => void}>).detail.resume, setMessage);
		};
		window.addEventListener("deployops-before-refresh", listener);
		return () => window.removeEventListener("deployops-before-refresh", listener);
	}, [autosave]);

	function update(next: BuilderDefinition) {setDef(next); autosave.edit(next);}
	function apply(action: Action) {update(history.apply(action));}
	useEffect(() => {
		const listener = (event: KeyboardEvent) => {
			const target = event.target as HTMLElement;
			if (panel || busy || deleting || tab !== "build" || target.closest("input,textarea,select,[contenteditable=true]")) return;
			if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {event.preventDefault(); update(event.shiftKey ? history.redo() : history.undo());}
			if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "y") {event.preventDefault(); update(history.redo());}
		}; window.addEventListener("keydown", listener); return () => window.removeEventListener("keydown", listener);
	});
	useEffect(() => {const warn = (event: BeforeUnloadEvent) => {if (autosave.state !== "saved") event.preventDefault();}; window.addEventListener("beforeunload", warn); return () => window.removeEventListener("beforeunload", warn);}, [autosave]);
	function add(type: string, target?: string, at?: number) {
		const section = def.sections.find(s => s.id === target) ?? def.sections.find(s => s.id === selected || s.fields.some(f => f.id === selected)) ?? def.sections[0];
		if (!section) return;
		const id = newId("f"), config = structuredClone(getPlugin(type).defaultConfig);
		for (const col of (config.columns ?? []) as ColumnDef[]) col.id = newId("f");
		const i = section.fields.findIndex(f => f.id === selected);
		apply({type: "addField", section: section.id, index: at ?? (i < 0 ? section.fields.length : i + 1), field: {id, key: `field_${id.slice(2)}`, type, label: fieldLabel(type, getPlugin(type).label), config}}); select(id);
	}
	function remove(id: string, section: boolean) {
		const ids = section ? def.sections.find(s => s.id === id)?.fields.map(f => f.id) ?? [] : [id];
		setDeleting({id, section, affected: dependencies(def, ids)});
	}
	const field = def.sections.flatMap(s => s.fields).find(f => f.id === selected), section = def.sections.find(s => s.id === selected);
	const shareable = isShareable(record);
	const locked = !!panel || busy;
	const tabs: [Tab, string][] = [["build", "Build"], ["entries", "Entries"], ["documents", "Documents"], ["appearance", "Appearance"], ...(jobForm ? [["rules", "Jobs"] as [Tab, string]] : [])];
	return <div className="builder-screen flex h-[calc(100svh-4rem)] flex-col">
		<header className="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-2.5">
			<Link to="/builder" aria-label="All forms" title="All forms" className="grid size-9 shrink-0 place-items-center rounded-lg text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50 hover:text-slate-900"><ArrowLeft className="size-4" /></Link>
			<div className="min-w-0 flex-1">
				<input aria-label="Form title" disabled={locked} value={def.title ?? ""} placeholder="Untitled form" onChange={e => apply({type: "setTitle", title: e.target.value})}
					className="w-full max-w-xl truncate rounded-md border border-transparent bg-transparent px-1.5 py-0.5 text-base font-semibold text-slate-900 hover:border-slate-200 focus:border-brand-500 focus:outline-none focus:ring-3 focus:ring-brand-500/15" />
				<div className="flex items-center gap-2 px-1.5 text-xs text-slate-500">
					<span className="inline-flex items-center gap-1">{jobForm ? <><Briefcase className="size-3" />Job checklist</> : <><Link2 className="size-3" />Shareable form</>}</span><span>·</span>
					<Badge kind={record.status}>{record.status}{record.versions[0] ? ` v${record.versions[0].version_no}` : ""}</Badge>
					<SaveState autosave={autosave} />
				</div>
			</div>
			{autosave.state === "conflict" && <Btn tone="danger" size="sm" onClick={() => setReloading(true)}>Reload</Btn>}
			{autosave.state === "error" && <Btn size="sm" onClick={() => void autosave.flush().catch(e => setMessage(e.message))}>Retry save</Btn>}
			{tab === "build" && <div className="flex items-center border-r border-slate-200 pr-2">
				<IconBtn label="Undo (Ctrl+Z)" disabled={locked || !history.canUndo} onClick={() => update(history.undo())}><Undo2 className="size-4" /></IconBtn>
				<IconBtn label="Redo (Ctrl+Shift+Z)" disabled={locked || !history.canRedo} onClick={() => update(history.redo())}><Redo2 className="size-4" /></IconBtn>
			</div>}
			<Btn tone="ghost" disabled={locked} icon={<Eye className="size-4" />} onClick={() => void openPanel("preview")}>Preview</Btn>
			<Btn tone="ghost" disabled={locked} icon={<History className="size-4" />} onClick={() => void openPanel("versions")}>Versions</Btn>
			{shareable && <Btn disabled={locked} icon={<Share2 className="size-4" />} onClick={() => setPanel("share")}>Share</Btn>}
			<Btn tone="primary" loading={busy && !panel} disabled={locked || autosave.state === "conflict"} icon={<Rocket className="size-4" />} onClick={() => void openPanel("publish")}>Publish</Btn>
		</header>
		<nav className="flex gap-1 border-b border-slate-200 bg-white px-4" role="tablist">{tabs.map(([t, label]) => <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
			className={`-mb-px border-b-2 px-3 py-2.5 text-sm font-medium transition ${tab === t ? "border-brand-500 text-brand-600" : "border-transparent text-slate-500 hover:text-slate-900"}`}>{label}</button>)}</nav>
		{(message || autosave.state === "conflict") && <div className="space-y-2 px-4 pt-3">
			{autosave.state === "conflict" && <Alert kind="warning">{`${autosave.modifiedBy} changed this form after you opened it. Reload to see their version; your unsaved edits here will be lost.`}</Alert>}
			{message && <Alert>{message}</Alert>}
		</div>}
		{tab === "build" && <fieldset disabled={locked} className="flex min-h-0 min-w-0 flex-1">
			<Canvas definition={def} catalog={catalog} selected={selected} select={select} apply={apply} add={add} remove={remove} />
			<aside className="w-[26rem] shrink-0 overflow-y-auto border-l border-slate-200 bg-white p-5" aria-label="Settings">
				{fieldError?.id === selected && <div className="mb-4"><Alert>{fieldError.message}</Alert></div>}
				{field ? <SettingsPanel key={field.id} field={field} definition={def} catalog={catalog} onChange={patch => apply({type: "updateField", id: field.id, patch})} />
				: section ? <div className="bld-form"><div className="border-b border-slate-200 pb-3"><h2 className="text-sm font-semibold text-slate-900">Step settings</h2><p className="text-xs text-slate-500">Each step is one screen of the form.</p></div>
					<label>Step title<input value={section.title ?? ""} onChange={e => apply({type: "updateSection", id: section.id, patch: {title: e.target.value}})} /></label>
					<label>Description <span className="font-normal text-slate-400">(optional)</span><textarea value={section.description ?? ""} placeholder="Shown under the title" onChange={e => apply({type: "updateSection", id: section.id, patch: {description: e.target.value}})} /></label></div>
				: <div className="flex flex-col items-center px-4 py-16 text-center text-sm text-slate-500"><MousePointerClick className="mb-3 size-8 text-slate-300" /><p className="font-medium text-slate-700">Nothing selected</p><p className="mt-1">Select a field or step to edit its settings.</p></div>}
			</aside>
		</fieldset>}
		<div className={tab === "build" ? "hidden" : "min-h-0 flex-1 overflow-y-auto bg-slate-50"}>
			{tab === "entries" && <Entries form={record.name} title={def.title || record.title} jobForm={jobForm} canShare={shareable} onShare={() => setPanel("share")} />}
			{tab === "documents" && <div className="mx-auto max-w-4xl px-8 py-6"><Documents form={record.name} definition={def} onAdd={value => apply({type: "appendReference", value})} onChange={value => apply({type: "references", value})} /></div>}
			{tab === "appearance" && <Appearance def={def} jobForm={jobForm} record={record} apply={apply} onMessage={setMessage} reload={reload} flush={() => autosave.flush()} />}
			{tab === "rules" && <div className="mx-auto max-w-5xl px-8 py-6"><Rules form={record.name} published={!!record.current_version} /></div>}
		</div>
		{panel === "preview" && <PreviewScreen definition={def} catalog={catalog} title={def.title} form={record.name} onClose={() => setPanel("")} />}
		{panel === "publish" && check && <Publish record={{...record, title: def.title || record.title}} check={check} definition={def} flush={() => autosave.flush()} onClose={() => setPanel("")} onPublished={reload} onChooseJobs={() => setTab("rules")}
			onSelect={(id, message) => {const target = errorTarget(def, id); select(target); setFieldError({id: target, message}); setPanel(""); setTab("build");}} />}
		{panel === "versions" && <Versions record={record} catalog={catalog} flush={() => autosave.flush()} token={() => autosave.latestModified} restore={reload} onClose={() => setPanel("")} />}
		<ShareDialog open={panel === "share"} form={record.name} title={def.title || record.title} onClose={() => setPanel("")} />
		<Confirm open={!!deleting} danger title={`Delete ${deleting?.section ? "step" : "field"}?`} confirmLabel="Delete" onClose={() => setDeleting(undefined)}
			onConfirm={() => {apply({type: deleting!.section ? "deleteSection" : "deleteField", id: deleting!.id}); select(""); setDeleting(undefined);}}
			message={<>{deleting?.section ? "The step and all its fields are removed from the draft." : "The field is removed from the draft."} You can undo this.{deleting?.affected.length ? <><span className="mt-3 block font-medium text-slate-800">These conditions use it and will be removed:</span><ul className="mt-1 list-disc pl-5">{deleting.affected.map(a => <li key={a}>{a}</li>)}</ul></> : null}</>} />
		<Confirm open={reloading} danger title="Reload the form?" confirmLabel="Reload" onClose={() => setReloading(false)} onConfirm={() => {setReloading(false); void reload();}} message="Your unsaved edits in this window are discarded and the latest saved version is loaded." />
	</div>;
}

function SaveState({autosave}: {autosave: Autosave<BuilderDefinition>}) {
	if (autosave.state === "saved") return <span className="inline-flex items-center gap-1 text-slate-500"><Check className="size-3" />Draft saved</span>;
	if (autosave.state === "conflict") return <span className="inline-flex items-center gap-1 font-medium text-red-600"><CloudOff className="size-3" />Changed by {autosave.modifiedBy}, reload</span>;
	if (autosave.state === "error") return <span className="inline-flex items-center gap-1 font-medium text-red-600" title={autosave.error}><CloudOff className="size-3" />Not saved</span>;
	return <span className="inline-flex items-center gap-1 text-slate-500"><Loader2 className="size-3 animate-spin" />Saving…</span>;
}

function Appearance({def, jobForm, record, apply, onMessage, reload, flush}: {def: BuilderDefinition; jobForm: boolean; record: FormRecord; apply: (a: Action) => void; onMessage: (m: string) => void; reload: () => Promise<unknown>; flush: () => Promise<void>}) {
	const set = (key: string, value: string) => apply({type: "appearance", value: {...def.appearance, [key]: value}});
	const [busy, setBusy] = useState(false);
	async function switchType() {
		setBusy(true);
		try {await flush(); await write("set_form_context", {form: record.name, context_doctype: jobForm ? null : "DeployOps Job"}); await reload();}
		catch (e) {onMessage(e instanceof Error ? e.message : String(e));} finally {setBusy(false);}
	}
	return <div className="mx-auto max-w-3xl space-y-6 px-8 py-6">
		<section className="rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
			<h2 className="font-semibold text-slate-900">Card</h2><p className="mb-5 text-sm text-slate-500">How the form appears in lists and on the home screen.</p>
			<div className="grid gap-4 sm:grid-cols-2">
				<div className="sm:col-span-2"><TextField label="Subtitle" placeholder="A short line under the title" value={String(def.appearance?.subtitle ?? "")} onChange={e => set("subtitle", e.target.value)} /></div>
				<TextField label="Icon" hint="A lucide icon name, e.g. clipboard-check" value={String(def.appearance?.icon ?? "")} onChange={e => set("icon", e.target.value)} />
				<label className="block"><span className="mb-1.5 block text-sm font-medium text-slate-700">Colour</span><div className="flex gap-2"><input type="color" aria-label="Pick colour" className="h-9 w-12 cursor-pointer rounded-lg border border-slate-300 bg-white p-1" value={/^#[0-9a-f]{6}$/i.test(String(def.appearance?.color)) ? String(def.appearance?.color) : "#2b7fff"} onChange={e => set("color", e.target.value)} /><input className="bld-input font-mono" value={String(def.appearance?.color ?? "")} placeholder="#2b7fff" onChange={e => set("color", e.target.value)} /></div></label>
			</div>
		</section>
		<section className="rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
			<h2 className="font-semibold text-slate-900">Form type</h2>
			<p className="mt-1 text-sm text-slate-500">{jobForm ? "Job checklist: filled on a job's machines and attached with Form Rules." : "Shareable form: filled from one link, any number of times."}</p>
			{record.versions.length === 0 ? <Btn className="mt-4" loading={busy} onClick={() => void switchType()}>{jobForm ? "Make it a shareable form" : "Make it a job checklist"}</Btn>
			: <p className="mt-3 text-xs text-slate-500">A published form can't change type. Use <strong>Duplicate</strong> on the forms list to make a copy of the other type.</p>}
		</section>
	</div>;
}

function parseDefinition(value: FormRecord["draft_definition"]): Definition {return typeof value === "string" ? JSON.parse(value) : value;}
