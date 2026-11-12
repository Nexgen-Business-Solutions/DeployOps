// A shareable form's link (/f/<form>): start a new entry each time, or continue one of your drafts.
import { ChevronRight, ClipboardList, Plus } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { Banner, Button, Page, Skeleton, TopBar } from "../components/ui";
import { post } from "../lib/api";
import { useApi } from "../lib/useApi";

type Info = {name: string; title: string; subtitle: string | null; can_start: boolean; reason: string | null; mine: {name: string; status: string; created: string; modified: string}[]};

const when = (v: string) => new Date(v.replace(" ", "T")).toLocaleString("en-GB", {day: "numeric", month: "short", hour: "2-digit", minute: "2-digit"});

export default function FillForm() {
	const {form = ""} = useParams(), navigate = useNavigate();
	const {data, error, loading} = useApi<Info>("forms_core.api.fill_info", {form});
	const [busy, setBusy] = useState(false), [startError, setStartError] = useState("");
	async function start() {
		setBusy(true); setStartError("");
		try {navigate(`/s/${encodeURIComponent(await post<string>("forms_core.api.start_submission", {form}))}`);}
		catch (e) {setStartError(e instanceof Error ? e.message : String(e)); setBusy(false);}
	}
	const drafts = data?.mine.filter(m => m.status === "Draft") ?? [], done = data?.mine.filter(m => m.status !== "Draft") ?? [];
	return <><TopBar title={data?.title ?? "Form"} back="/" />
		<Page>{error ? <Banner>{error.message}</Banner> : loading && !data ? <Skeleton className="h-48" /> : data && <div className="space-y-8">
			<header className="flex items-start gap-4">
				<span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-brand-50 text-brand-600"><ClipboardList className="size-6" /></span>
				<div><h1 className="text-2xl font-semibold tracking-tight">{data.title}</h1>{data.subtitle && <p className="mt-1 text-muted">{data.subtitle}</p>}</div>
			</header>
			{data.can_start ? <div className="space-y-3"><Button className="w-full sm:w-auto" loading={busy} icon={<Plus className="size-4" />} onClick={() => void start()}>Start a new entry</Button>{startError && <Banner>{startError}</Banner>}</div> : <Banner kind="warning">{data.reason}</Banner>}
			{drafts.length > 0 && <List title="Continue a draft" items={drafts} action="Continue" />}
			{done.length > 0 && <List title="Your submitted entries" items={done} action="View" />}
		</div>}</Page></>;
}

function List({title, items, action}: {title: string; items: Info["mine"]; action: string}) {
	return <section><h2 className="eyebrow mb-2">{title}</h2><ul className="divide-y divide-line overflow-hidden rounded-2xl ring-1 ring-line">{items.map(m => <li key={m.name}>
		<Link to={`/s/${encodeURIComponent(m.name)}`} className="flex items-center gap-3 px-4 py-3.5 hover:bg-soft">
			<span className="min-w-0 flex-1"><span className="block font-mono text-sm">{m.name}</span><span className="block text-xs text-muted">Started {when(m.created)} · updated {when(m.modified)}</span></span>
			<span className="text-sm font-medium text-brand-600">{action}</span><ChevronRight className="size-4 text-zinc-400" />
		</Link></li>)}</ul></section>;
}
