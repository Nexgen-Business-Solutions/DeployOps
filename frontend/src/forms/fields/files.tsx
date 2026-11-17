import { useEffect, useRef, useState } from "react";
import { resizeImage } from "../../lib/image";
import type { FieldInputProps } from "./index";
const NO_ENTRIES: Entry[] = [];
type Entry = {
	file: string;
	caption: string | null;
};
export function FilesInput({ field, value, disabled, ctx, onChange, inputId }: FieldInputProps) {
	const entries = (value ?? NO_ENTRIES) as Entry[], latest = useRef(entries), input = useRef<HTMLInputElement>(null), urls = useRef<string[]>([]);
	useEffect(() => { latest.current = entries; }, [entries]);
	const [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null), [dragging, setDragging] = useState(false);
	const c = field.config ?? {}, photos = field.type === "photos", max = typeof c.max === "number" ? c.max : Infinity;
	useEffect(() => () => { urls.current.forEach(url => URL.revokeObjectURL(url)); }, []);
	async function add(files: File[]) {
		if (disabled || busy)
			return;
		setBusy(true);
		setError(null);
		try {
			for (const file of files) {
				if (latest.current.length >= max)
					break;
				if (photos && !file.type.startsWith("image/"))
					continue;
				const blob = photos ? await resizeImage(file) : file;
				const filename = blob === file ? file.name : file.name.replace(/\.[^.]+$/, "") + ".jpg";
				const url = ctx.upload ? await ctx.upload(blob, filename, field.id) : URL.createObjectURL(blob);
				if (!ctx.upload)
					urls.current.push(url);
				latest.current = [...latest.current, { file: url, caption: null }];
				onChange(latest.current);
			}
		}
		catch (e) {
			setError(e instanceof Error ? e.message : "A file could not be uploaded.");
		}
		finally {
			setBusy(false);
		}
	}
	return <div onDragOver={e => {
		if (!disabled && !busy) {
			e.preventDefault();
			setDragging(true);
		}
	}} onDragLeave={() => setDragging(false)} onDrop={e => { e.preventDefault(); setDragging(false); void add(Array.from(e.dataTransfer.files)); }} className={dragging ? "rounded-2xl ring-2 ring-brand-500" : ""}>
		<div className={photos ? "grid grid-cols-2 gap-3" : "space-y-3"}>{entries.map((entry, i) => <div key={`${i}-${entry.file}`} className="rounded-2xl border border-line p-3">{photos ? <a href={entry.file} target="_blank" rel="noreferrer"><img src={entry.file} alt={entry.caption ?? "Photo evidence"} className="aspect-square w-full rounded-xl object-cover" /></a> : <a href={entry.file} target="_blank" rel="noreferrer" className="break-all text-brand-500">{decodeURIComponent(entry.file.split("/").at(-1) ?? "File")}</a>}{c.captions === true && <input className="field-input mt-2" disabled={disabled} aria-label="Caption" value={entry.caption ?? ""} onChange={e => onChange(entries.map((v, n) => n === i ? { ...v, caption: e.target.value || null } : v))} />} {!disabled && <button type="button" className="mt-2 text-sm text-muted" onClick={() => onChange(entries.filter((_, n) => n !== i))}>Remove</button>}</div>)}</div>
		<input ref={input} id={inputId} type="file" multiple hidden disabled={disabled || busy} accept={photos ? "image/*" : (c.extensions as string[] | undefined)?.map(e => "." + e.replace(/^\./, "")).join(",")} onChange={e => { void add(Array.from(e.target.files ?? [])); e.target.value = ""; }} />
		{!disabled && entries.length < max && <button type="button" disabled={busy} onClick={() => input.current?.click()} className="mt-3 rounded-xl border border-dashed border-zinc-300 px-5 py-4 text-brand-500">{busy ? "Uploading…" : photos ? "+ Add photos" : "+ Add files"}</button>}
		<p className="mt-2 text-sm text-muted">{entries.length} of {Number(c.min ?? 0)} minimum{!ctx.upload && ctx.mode === "preview" ? " · Uploads are off in preview" : ""}</p>{error && <p role="alert" className="text-sm text-red-600">{error}</p>}
	</div>;
}

