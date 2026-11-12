// Builder UI kit: compact desk-style controls for designers (laptop and tablet first).
import { Check, Copy, Loader2, Share2, X } from "lucide-react";
import { type ButtonHTMLAttributes, type ReactNode, useEffect, useRef, useState } from "react";

type Tone = "primary" | "secondary" | "ghost" | "danger";
const TONES: Record<Tone, string> = {
	primary: "bg-brand-500 text-white shadow-sm hover:bg-brand-600",
	secondary: "bg-white text-slate-700 ring-1 ring-slate-300 shadow-xs hover:bg-slate-50 hover:text-slate-900",
	ghost: "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
	danger: "bg-red-600 text-white shadow-sm hover:bg-red-700",
};

export function Btn({tone = "secondary", size = "md", icon, loading, className = "", children, disabled, ...props}: ButtonHTMLAttributes<HTMLButtonElement> & {tone?: Tone; size?: "sm" | "md"; icon?: ReactNode; loading?: boolean}) {
	const sizing = size === "sm" ? "h-8 px-2.5 text-[13px] gap-1.5" : "h-9 px-3.5 text-sm gap-2";
	return <button type="button" {...props} disabled={disabled || loading} className={`inline-flex shrink-0 items-center justify-center rounded-lg font-medium transition active:scale-[0.98] disabled:pointer-events-none disabled:opacity-45 ${sizing} ${TONES[tone]} ${className}`}>
		{loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : icon}{children}
	</button>;
}

export function IconBtn({label, children, className = "", ...props}: ButtonHTMLAttributes<HTMLButtonElement> & {label: string}) {
	return <button type="button" aria-label={label} title={label} {...props} className={`grid size-8 shrink-0 place-items-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 disabled:pointer-events-none disabled:opacity-35 ${className}`}>{children}</button>;
}

const BADGES = {
	Draft: "bg-slate-100 text-slate-700 ring-slate-200",
	Published: "bg-emerald-50 text-emerald-700 ring-emerald-200",
	Submitted: "bg-emerald-50 text-emerald-700 ring-emerald-200",
	Archived: "bg-zinc-100 text-zinc-500 ring-zinc-200",
	Cancelled: "bg-zinc-100 text-zinc-500 ring-zinc-200",
	info: "bg-blue-50 text-blue-700 ring-blue-200",
	warning: "bg-amber-50 text-amber-800 ring-amber-200",
} as const;
export function Badge({kind, children}: {kind: string; children?: ReactNode}) {
	const style = BADGES[kind as keyof typeof BADGES] ?? BADGES.Draft;
	return <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${style}`}>{children ?? kind}</span>;
}

/** Centred modal with a header, scrolling body and an optional footer. */
export function Modal({open, title, description, size = "md", onClose, footer, children}: {open: boolean; title: ReactNode; description?: ReactNode; size?: "sm" | "md" | "lg" | "xl"; onClose: () => void; footer?: ReactNode; children: ReactNode}) {
	const ref = useRef<HTMLDivElement>(null), close = useRef(onClose);
	useEffect(() => {close.current = onClose;});
	useEffect(() => {
		if (!open) return;
		const onKey = (e: KeyboardEvent) => {if (e.key === "Escape") close.current();};
		window.addEventListener("keydown", onKey);
		if (!ref.current?.contains(document.activeElement)) ref.current?.querySelector<HTMLElement>("input:not([type=hidden]):not(.sr-only),select,textarea")?.focus();
		return () => window.removeEventListener("keydown", onKey);
	}, [open]);
	if (!open) return null;
	const width = {sm: "max-w-md", md: "max-w-xl", lg: "max-w-3xl", xl: "max-w-6xl"}[size];
	return <div className="fixed inset-0 z-50 flex items-start justify-center bg-slate-950/40 p-4 pt-[8vh] backdrop-blur-[2px]" onMouseDown={onClose}>
		<div ref={ref} role="dialog" aria-modal="true" aria-label={typeof title === "string" ? title : undefined} onMouseDown={e => e.stopPropagation()} className={`flex max-h-[min(86svh,56rem)] w-full ${width} flex-col overflow-hidden rounded-2xl bg-white shadow-2xl ring-1 ring-slate-900/5`}>
			<header className="flex items-start gap-3 border-b border-slate-200 px-6 py-4">
				<div className="min-w-0 flex-1"><h2 className="text-lg font-semibold text-slate-900">{title}</h2>{description && <p className="mt-0.5 text-sm text-slate-500">{description}</p>}</div>
				<IconBtn label="Close" onClick={onClose}><X className="size-4" /></IconBtn>
			</header>
			<div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">{children}</div>
			{footer && <footer className="flex items-center justify-end gap-2 border-t border-slate-200 bg-slate-50 px-6 py-3">{footer}</footer>}
		</div>
	</div>;
}

export function Confirm({open, title, message, confirmLabel, danger, busy, onConfirm, onClose}: {open: boolean; title: string; message: ReactNode; confirmLabel: string; danger?: boolean; busy?: boolean; onConfirm: () => void; onClose: () => void}) {
	return <Modal open={open} title={title} size="sm" onClose={onClose} footer={<><Btn onClick={onClose}>Cancel</Btn><Btn tone={danger ? "danger" : "primary"} loading={busy} onClick={onConfirm}>{confirmLabel}</Btn></>}>
		<div className="text-sm leading-relaxed text-slate-600">{message}</div>
	</Modal>;
}

export function Alert({kind = "error", children}: {kind?: "error" | "success" | "info" | "warning"; children: ReactNode}) {
	const style = {error: "bg-red-50 text-red-800 ring-red-200", success: "bg-emerald-50 text-emerald-800 ring-emerald-200", info: "bg-blue-50 text-blue-800 ring-blue-200", warning: "bg-amber-50 text-amber-900 ring-amber-200"}[kind];
	return <div role={kind === "error" ? "alert" : "status"} className={`whitespace-pre-line rounded-lg px-3.5 py-2.5 text-sm ring-1 ring-inset ${style}`}>{children}</div>;
}

export function TextField({label, hint, ...props}: React.InputHTMLAttributes<HTMLInputElement> & {label: string; hint?: string}) {
	return <label className="block"><span className="mb-1.5 block text-sm font-medium text-slate-700">{label}</span><input {...props} className="bld-input" />{hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}</label>;
}

/** Radio cards: one option per card, with an icon, a title and a sentence. */
export function ChoiceCards<T extends string>({value, options, onChange, columns = 2}: {value: T; options: {value: T; title: string; text: string; icon: ReactNode; disabled?: boolean}[]; onChange: (value: T) => void; columns?: 2 | 3}) {
	return <div role="radiogroup" className={`grid gap-3 ${columns === 3 ? "sm:grid-cols-3" : "sm:grid-cols-2"}`}>{options.map(o => <button key={o.value} type="button" role="radio" aria-checked={value === o.value} disabled={o.disabled} onClick={() => onChange(o.value)} className={`flex gap-3 rounded-xl p-4 text-left ring-1 transition disabled:cursor-not-allowed disabled:opacity-50 ${value === o.value ? "bg-brand-50/60 ring-2 ring-brand-500" : "ring-slate-200 hover:bg-slate-50 hover:ring-slate-300"}`}>
		<span className={`grid size-9 shrink-0 place-items-center rounded-lg ${value === o.value ? "bg-brand-500 text-white" : "bg-slate-100 text-slate-600"}`}>{o.icon}</span>
		<span><span className="block text-sm font-semibold text-slate-900">{o.title}</span><span className="mt-0.5 block text-[13px] leading-snug text-slate-500">{o.text}</span></span>
	</button>)}</div>;
}

export async function copyText(text: string): Promise<boolean> {
	try {await navigator.clipboard.writeText(text); return true;}
	catch {
		const area = document.createElement("textarea"); area.value = text; document.body.appendChild(area); area.select();
		const ok = document.execCommand("copy"); area.remove(); return ok;
	}
}

/** The share link with Copy and (where the device supports it) Share buttons. */
export function ShareLink({url, title}: {url: string; title: string}) {
	const [copied, setCopied] = useState(false);
	const canShare = typeof navigator !== "undefined" && "share" in navigator;
	return <div className="flex items-center gap-2">
		<input readOnly value={url} aria-label="Form link" onFocus={e => e.target.select()} className="bld-input flex-1 font-mono text-[13px]" />
		<Btn tone="primary" icon={copied ? <Check className="size-4" /> : <Copy className="size-4" />} onClick={() => void copyText(url).then(ok => {if (ok) {setCopied(true); setTimeout(() => setCopied(false), 1800);}})}>{copied ? "Copied" : "Copy link"}</Btn>
		{canShare && <Btn icon={<Share2 className="size-4" />} onClick={() => void navigator.share({title, url}).catch(() => {})}>Share</Btn>}
	</div>;
}

export function Spinner({label = "Loading"}: {label?: string}) {
	return <div className="flex items-center justify-center gap-2 py-16 text-sm text-slate-500"><Loader2 className="size-4 animate-spin" aria-hidden />{label}…</div>;
}

export function formatDate(value?: string | null, withTime = false): string {
	if (!value) return "—";
	const d = new Date(value.replace(" ", "T"));
	if (Number.isNaN(d.getTime())) return value;
	return d.toLocaleString("en-GB", withTime ? {day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit"} : {day: "numeric", month: "short", year: "numeric"});
}
