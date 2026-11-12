import { Monitor, RotateCcw, Smartphone, Tablet, Wand2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { FormRenderer } from "../forms/FormRenderer";
import type { Definition, Answers } from "../forms/types";
import type { Catalog } from "./api";
import { sampleValues } from "./sample";
import { Btn, IconBtn } from "./kit";
import { documentUrl } from "./Documents";

// Each size is a screen: a fixed frame whose content scrolls inside it, like the real device.
const SIZES = [
	{w: 375, h: 812, label: "Phone", icon: Smartphone, frame: "rounded-[2rem]"},
	{w: 768, h: 1024, label: "Tablet", icon: Tablet, frame: "rounded-3xl"},
	{w: 1200, h: 0, label: "Desktop", icon: Monitor, frame: "rounded-xl"},
];

function usePreviewState() {
	const [width, setWidth] = useState(375), [answers, setAnswers] = useState<Answers>({}), [values, setValues] = useState<Record<string, unknown>>({});
	return {width, setWidth, answers, setAnswers, values, setValues, reset: () => {setValues({}); setAnswers({});}};
}

function SizePicker({width, onChange}: {width: number; onChange: (w: number) => void}) {
	return <div role="radiogroup" aria-label="Screen size" className="flex rounded-lg bg-slate-200/70 p-1">{SIZES.map(({w, label, icon: Icon}) => <button key={w} type="button" role="radio" aria-checked={width === w} title={`${label} (${w}px)`} onClick={() => onChange(w)}
		className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition ${width === w ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"}`}><Icon className="size-4" /><span className="hidden sm:inline">{label}</span><span className="hidden text-xs text-slate-400 md:inline">{w}</span></button>)}</div>;
}

// Designers open a form's documents through the builder endpoint; a private file URL is refused to non-admins.
function Screen({definition, readonly, state, form}: {definition: Definition; readonly: boolean; state: ReturnType<typeof usePreviewState>; form?: string}) {
	return <FormRenderer definition={definition} answers={state.answers} ctx={{mode: readonly ? "readonly" : "preview", values: state.values}}
		references={(definition.references ?? []).map(r => ({title: r.title, url: form ? documentUrl(form, r.file) : r.file, show_in: r.show_in}))}
		onChange={(id, value) => state.setAnswers(a => ({...a, [id]: value}))} />;
}

/** Inline preview, used inside other dialogs (a version's read-only view). */
export function Preview({definition, catalog, readonly = false, form}: {definition: Definition; catalog: Catalog; readonly?: boolean; form?: string}) {
	const state = usePreviewState();
	return <div className="space-y-4">
		<div className="flex flex-wrap items-center gap-2">
			<SizePicker width={state.width} onChange={state.setWidth} />
			<span className="flex-1" />
			{!readonly && catalog.values.length > 0 && <Btn size="sm" icon={<Wand2 className="size-3.5" />} onClick={() => state.setValues(sampleValues(catalog))}>Fill sample job</Btn>}
			{!readonly && <Btn size="sm" tone="ghost" icon={<RotateCcw className="size-3.5" />} onClick={state.reset}>Reset</Btn>}
		</div>
		<p className="text-xs text-slate-500">{readonly ? "Read-only view of this version." : "Try the form as it will appear. Nothing you enter here is saved."}</p>
		<div className="overflow-auto rounded-xl bg-slate-100 p-6"><div style={{width: state.width, minWidth: state.width}} className="mx-auto rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
			<Screen definition={definition} readonly={readonly} state={state} form={form} />
		</div></div>
	</div>;
}

/** Full-screen preview: a toolbar and a centred device frame that scrolls inside, so the page itself never moves. */
export function PreviewScreen({definition, catalog, title, form, onClose}: {definition: Definition; catalog: Catalog; title?: string; form?: string; onClose: () => void}) {
	const state = usePreviewState();
	const size = SIZES.find(s => s.w === state.width) ?? SIZES[0];
	const close = useRef(onClose), scroller = useRef<HTMLDivElement>(null);
	useEffect(() => {close.current = onClose;});
	useEffect(() => {
		const onKey = (e: KeyboardEvent) => {if (e.key === "Escape") close.current();};
		const overflow = document.body.style.overflow;
		document.body.style.overflow = "hidden";
		window.addEventListener("keydown", onKey);
		return () => {window.removeEventListener("keydown", onKey); document.body.style.overflow = overflow;};
	}, []);
	useEffect(() => {scroller.current?.scrollTo({top: 0});}, [state.width]);
	return <div role="dialog" aria-modal="true" aria-label="Preview" className="fixed inset-0 z-50 flex flex-col bg-slate-100">
		<header className="grid shrink-0 grid-cols-[1fr_auto_1fr] items-center gap-3 px-4 py-3 sm:px-6">
			<div className="min-w-0"><h2 className="text-sm font-semibold text-slate-900">Preview</h2><p className="truncate text-xs text-slate-500">{title || "Untitled form"} · nothing you enter is saved</p></div>
			<SizePicker width={state.width} onChange={state.setWidth} />
			<div className="flex items-center justify-end gap-1">
				{catalog.values.length > 0 && <Btn size="sm" icon={<Wand2 className="size-3.5" />} onClick={() => state.setValues(sampleValues(catalog))}>Fill sample job</Btn>}
				<Btn size="sm" tone="ghost" icon={<RotateCcw className="size-3.5" />} onClick={state.reset}>Reset</Btn>
				<IconBtn label="Close preview" onClick={onClose}><X className="size-4" /></IconBtn>
			</div>
		</header>
		<div className="flex min-h-0 flex-1 items-center justify-center overflow-x-auto px-4 pb-6 sm:px-8">
			<div ref={scroller} aria-label={`${size.label} screen`} style={{width: size.w, maxHeight: size.h || undefined}}
				className={`h-full max-w-full shrink-0 overflow-y-auto overscroll-contain bg-white shadow-xl ring-1 ring-slate-900/10 ${size.frame}`}>
				<div className="p-6"><h1 className="text-xl font-semibold text-slate-900">{title || "Untitled form"}</h1><Screen definition={definition} readonly={false} state={state} form={form} /></div>
			</div>
		</div>
	</div>;
}
