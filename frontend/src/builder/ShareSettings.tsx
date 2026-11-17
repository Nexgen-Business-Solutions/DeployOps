// "Who can fill this form?" for a share form: anyone with the link, chosen roles, or chosen people,
// and whether each person (or device, on public forms) may send it once or many times.
import { Globe, ShieldCheck, Users, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { read, shareUrl, write } from "./api";
import { Alert, ShareLink, Spinner } from "./kit";
import { ONCE_PUBLIC_NOTE, sharePayload, type Audience, type AudienceOption, type Search, type ShareValue } from "./share";

const searchAudience: Search = (kind, txt) => read<AudienceOption[]>("search_audience", {kind, txt});

/** Chips and a search box in one field; matches drop down below it. */
function Picker({kind, chips, onAdd, onRemove, search}: {kind: "role" | "user"; chips: {key: string; label: string}[]; onAdd: (o: AudienceOption) => void; onRemove: (key: string) => void; search: Search}) {
	const [txt, setTxt] = useState(""), [options, setOptions] = useState<AudienceOption[]>([]), [open, setOpen] = useState(false);
	const seq = useRef(0), input = useRef<HTMLInputElement>(null);
	useEffect(() => {
		if (!open) return;
		const n = ++seq.current;
		const t = setTimeout(() => void search(kind, txt).then(rows => {if (n === seq.current) setOptions(rows);}).catch(() => {}), 200);
		return () => clearTimeout(t);
	}, [kind, txt, open, search]);
	const taken = new Set(chips.map(c => c.key)), shown = options.filter(o => !taken.has(o.value));
	return <div className="relative">
		<div onClick={() => input.current?.focus()} className="flex min-h-10 cursor-text flex-wrap items-center gap-1.5 rounded-lg bg-white px-2 py-1.5 ring-1 ring-slate-300 focus-within:ring-2 focus-within:ring-brand-500">
			{chips.map(c => <span key={c.key} className="inline-flex items-center gap-1 rounded-md bg-slate-100 py-0.5 pl-2 pr-0.5 text-[13px] font-medium text-slate-700">{c.label}
				<button type="button" aria-label={`Remove ${c.label}`} onClick={e => {e.stopPropagation(); onRemove(c.key);}} className="grid size-5 place-items-center rounded text-slate-400 hover:bg-slate-200 hover:text-slate-700"><X className="size-3" /></button></span>)}
			<input ref={input} className="min-w-32 flex-1 border-0 bg-transparent px-1 py-0.5 text-sm outline-none placeholder:text-slate-400" placeholder={chips.length ? "Add more…" : kind === "role" ? "Search roles…" : "Search people…"}
				value={txt} onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 150)} onChange={e => setTxt(e.target.value)}
				onKeyDown={e => {if (e.key === "Backspace" && !txt && chips.length) onRemove(chips[chips.length - 1].key);}} />
		</div>
		{open && shown.length > 0 && <ul className="absolute z-10 mt-1 max-h-56 w-full overflow-auto rounded-lg bg-white py-1 shadow-lg ring-1 ring-slate-200">
			{shown.map(o => <li key={o.value}><button type="button" className="flex w-full items-baseline gap-2 px-3 py-2 text-left text-sm hover:bg-slate-50" onMouseDown={e => e.preventDefault()} onClick={() => {onAdd(o); setTxt("");}}>
				<span className="font-medium text-slate-900">{o.label ?? o.value}</span>{o.email && o.email !== o.label && <span className="truncate text-xs text-slate-500">{o.email}</span>}</button></li>)}
		</ul>}
	</div>;
}

const AUDIENCES: {value: Audience; label: string; hint: string; icon: typeof Globe}[] = [
	{value: "Public", label: "Anyone", hint: "Anyone with the link, no login needed.", icon: Globe},
	{value: "Roles", label: "Roles", hint: "Signed-in people with any of these roles.", icon: ShieldCheck},
	{value: "Users", label: "People", hint: "Only the people you pick, after signing in.", icon: Users},
];

/** The settings themselves, without loading or saving (kept separate so it can be rendered in tests). */
export function ShareSettingsView({value, error, saving, onChange, search}: {form: string; title: string; value: ShareValue; error: string; saving: boolean; onChange: (v: ShareValue) => void; search: Search}) {
	const current = AUDIENCES.find(a => a.value === value.audience) ?? AUDIENCES[0], once = value.entry_limit === "Once";
	return <div className="space-y-5">
		<section className="space-y-2.5">
			<div className="flex items-center justify-between"><h3 className="text-sm font-semibold text-slate-900">Who can fill it</h3>{saving && <span className="text-xs text-slate-400">Saving…</span>}</div>
			<div role="radiogroup" aria-label="Who can fill it" className="grid grid-cols-3 rounded-lg bg-slate-100 p-1">{AUDIENCES.map(({value: v, label, icon: Icon}) =>
				<button key={v} type="button" role="radio" aria-checked={value.audience === v} onClick={() => onChange({...value, audience: v})}
					className={`flex items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-sm font-medium transition ${value.audience === v ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"}`}><Icon className="size-4" />{label}</button>)}</div>
			<p className="text-[13px] text-slate-500">{current.hint}</p>
			{value.audience === "Roles" && <Picker kind="role" search={search} chips={value.roles.map(r => ({key: r, label: r}))}
				onAdd={o => onChange({...value, roles: [...value.roles, o.value]})} onRemove={key => onChange({...value, roles: value.roles.filter(r => r !== key)})} />}
			{value.audience === "Users" && <Picker kind="user" search={search} chips={value.users.map(u => ({key: u.user, label: u.full_name || u.user}))}
				onAdd={o => onChange({...value, users: [...value.users, {user: o.value, full_name: o.label ?? o.value}]})} onRemove={key => onChange({...value, users: value.users.filter(u => u.user !== key)})} />}
		</section>
		<section className="flex items-start gap-3 border-t border-slate-200 pt-4">
			<div className="min-w-0 flex-1">
				<p className="text-sm font-semibold text-slate-900">One entry only</p>
				<p className="mt-0.5 text-[13px] text-slate-500">{once ? (value.audience === "Public" ? ONCE_PUBLIC_NOTE : "Each person can send it once.") : "Off: people can send it as many times as they like."}</p>
			</div>
			<button type="button" role="switch" aria-checked={once} aria-label="One entry only" onClick={() => onChange({...value, entry_limit: once ? "Multiple" : "Once"})}
				className={`relative mt-0.5 h-6 w-11 shrink-0 rounded-full transition ${once ? "bg-brand-500" : "bg-slate-300"}`}><span className={`absolute top-0.5 size-5 rounded-full bg-white shadow transition-all ${once ? "left-[22px]" : "left-0.5"}`} /></button>
		</section>
		{error && <Alert>{error}</Alert>}
	</div>;
}

/** Loads the form's settings and saves each change. An incomplete list (no role or person yet) is kept here until it's valid. */
export function ShareSettings({form, title, onSaved}: {form: string; title: string; onSaved?: (v: ShareValue) => void}) {
	const [value, setValue] = useState<ShareValue | null>(null), [error, setError] = useState(""), [saving, setSaving] = useState(false);
	useEffect(() => {
		let live = true;
		read<{share: ShareValue}>("get_form", {form}).then(doc => {if (live) setValue(doc.share);}).catch((e: unknown) => {if (live) setError(e instanceof Error ? e.message : String(e));});
		return () => {live = false;};
	}, [form]);
	async function change(next: ShareValue) {
		setValue(next); setError("");
		if ((next.audience === "Roles" && !next.roles.length) || (next.audience === "Users" && !next.users.length)) {
			setError(next.audience === "Roles" ? "Add at least one role." : "Add at least one person.");
			return;
		}
		setSaving(true);
		try {
			const saved = await write<ShareValue>("set_share_settings", sharePayload(form, next));
			setValue(saved); onSaved?.(saved);
		} catch (e) {setError(e instanceof Error ? e.message : String(e));}
		finally {setSaving(false);}
	}
	if (!value) return error ? <Alert>{error}</Alert> : <Spinner />;
	return <ShareSettingsView form={form} title={title} value={value} error={error} saving={saving} onChange={v => void change(v)} search={searchAudience} />;
}

/** Settings plus the link, as shown in the Share dialog and after publishing. */
export function SharePanel({form, title}: {form: string; title: string}) {
	return <div className="space-y-5">
		<ShareSettings form={form} title={title} />
		<section className="space-y-2.5 border-t border-slate-200 pt-4">
			<h3 className="text-sm font-semibold text-slate-900">Link</h3>
			<ShareLink url={shareUrl(form)} title={title} />
			<p className="text-[13px] text-slate-500">Answers show up under <strong className="font-medium text-slate-700">Entries</strong>.</p>
		</section>
	</div>;
}
