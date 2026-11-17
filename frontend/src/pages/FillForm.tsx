// A shareable form's link (/f/<form>), outside the signed-in app shell. Guests on a public form fill
// it in the browser (PublicFill); a restricted form asks them to sign in; signed-in people start or
// continue entries.
import { ChevronRight, ClipboardList, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { Banner, Button, Page, Skeleton } from "../components/ui";
import { deviceIds } from "../forms/publicFill";
import { get, post } from "../lib/api";
import Login from "./Login";
import { PublicFill, type PublicInfo } from "./PublicFill";
import { entryPath, fillView } from "./fillRoutes";

type Info = PublicInfo;

function signedIn(): boolean {
	const match = document.cookie.match(/(?:^|;\s*)user_id=([^;]*)/);
	const user = match ? decodeURIComponent(match[1]) : "Guest";
	return !!user && user !== "Guest";
}

/** fill_info with this browser's IDs, so a "once" form can say "already filled" up front. */
function useFillInfo(form: string) {
	const [data, setData] = useState<Info | null>(null), [error, setError] = useState<Error | null>(null);
	useEffect(() => {
		let live = true;
		deviceIds()
			.then(ids => get<Info>("forms_core.api.fill_info", {form, ...ids}))
			.then(info => {if (live) setData(info);}, (e: unknown) => {if (live) setError(e instanceof Error ? e : new Error(String(e)));});
		return () => {live = false;};
	}, [form]);
	return {data, error, loading: !data && !error};
}

const when = (v: string) => new Date(v.replace(" ", "T")).toLocaleString("en-GB", {day: "numeric", month: "short", hour: "2-digit", minute: "2-digit"});

export default function FillForm() {
	const {form = ""} = useParams(), navigate = useNavigate();
	const {data, error, loading} = useFillInfo(form);
	const [busy, setBusy] = useState(false), [startError, setStartError] = useState("");
	async function start() {
		setBusy(true); setStartError("");
		try {navigate(entryPath(form, await post<string>("forms_core.api.start_submission", {form})));}
		catch (e) {setStartError(e instanceof Error ? e.message : String(e)); setBusy(false);}
	}
	const view = data ? fillView(data, signedIn()) : null;
	if (data && view === "login") return <Login signedInAs={undefined} />;
	if (data && view === "public") return <PublicFill info={data} />;
	const drafts = data?.mine.filter(m => m.status === "Draft") ?? [], done = data?.mine.filter(m => m.status !== "Draft") ?? [];
	return <>
		<Page>{error ? <Banner>{error.message}</Banner> : loading && !data ? <Skeleton className="h-48" /> : data && <div className="space-y-8">
			<header className="flex items-start gap-4">
				<span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-brand-50 text-brand-600"><ClipboardList className="size-6" /></span>
				<div><h1 className="text-2xl font-semibold tracking-tight">{data.title}</h1>{data.subtitle && <p className="mt-1 text-muted">{data.subtitle}</p>}</div>
			</header>
			{data.can_start ? <div className="space-y-3"><Button className="w-full sm:w-auto" loading={busy} icon={<Plus className="size-4" />} onClick={() => void start()}>Start a new entry</Button>{startError && <Banner>{startError}</Banner>}</div> : <Banner kind="warning">{data.reason}</Banner>}
			{drafts.length > 0 && <List form={form} title="Continue a draft" items={drafts} action="Continue" />}
			{done.length > 0 && <List form={form} title="Your submitted entries" items={done} action="View" />}
		</div>}</Page></>;
}

function List({form, title, items, action}: {form: string; title: string; items: Info["mine"]; action: string}) {
	return <section><h2 className="eyebrow mb-2">{title}</h2><ul className="divide-y divide-line overflow-hidden rounded-2xl ring-1 ring-line">{items.map(m => <li key={m.name}>
		<Link to={entryPath(form, m.name)} className="flex items-center gap-3 px-4 py-3.5 hover:bg-soft">
			<span className="min-w-0 flex-1"><span className="block font-mono text-sm">{m.name}</span><span className="block text-xs text-muted">Started {when(m.created)} · updated {when(m.modified)}</span></span>
			<span className="text-sm font-medium text-brand-600">{action}</span><ChevronRight className="size-4 text-zinc-400" />
		</Link></li>)}</ul></section>;
}
