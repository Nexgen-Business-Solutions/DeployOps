import { FileText, Loader2, Plus, X } from "lucide-react";
import { useRef, useState } from "react";

import { ApiError, uploadPrivateFile } from "../../lib/api";
import { resizeImage } from "../../lib/image";
import type { Row, TableInfo } from "../../lib/types";

/** Photo or file evidence: private uploads attached to the form, one table row per file. */
export function FilesField({
	table,
	rows,
	disabled,
	doctype,
	docname,
	onChange,
}: {
	table: TableInfo;
	rows: Row[];
	disabled: boolean;
	doctype: string;
	docname: string;
	onChange: (rows: Row[]) => void;
}) {
	const input = useRef<HTMLInputElement>(null);
	const [uploading, setUploading] = useState(0);
	const [error, setError] = useState<string | null>(null);
	const [dragging, setDragging] = useState(false);
	const photos = table.kind === "photos";
	const column = table.file_column ?? (photos ? "image" : "file");

	async function add(files: FileList | File[]) {
		const list = Array.from(files).filter((file) => !photos || file.type.startsWith("image/"));
		if (!list.length) return;
		setError(null);
		setUploading(list.length);
		const added: Row[] = [];
		for (const file of list) {
			try {
				const blob = photos ? await resizeImage(file) : file;
				const name = blob === file ? file.name : `${file.name.replace(/\.[^.]+$/, "")}.jpg`;
				added.push({ [column]: await uploadPrivateFile(blob, name, doctype, docname), caption: photos ? null : file.name });
			} catch (e) {
				setError(e instanceof ApiError ? e.message : "A file could not be uploaded.");
			} finally {
				setUploading((n) => n - 1);
			}
		}
		if (added.length) onChange([...rows, ...added]);
	}

	const urls = rows.map((row) => String(row[column] ?? "")).filter(Boolean);
	const count = urls.length;
	const minimum = table.min_rows;

	return (
		<div
			onDragOver={(e) => {
				if (disabled) return;
				e.preventDefault();
				setDragging(true);
			}}
			onDragLeave={() => setDragging(false)}
			onDrop={(e) => {
				e.preventDefault();
				setDragging(false);
				if (!disabled) void add(e.dataTransfer.files);
			}}
			className={`rounded-2xl transition ${dragging ? "bg-brand-50 ring-2 ring-brand-500" : ""}`}
		>
			{photos ? (
				<ul className="grid grid-cols-3 gap-2 sm:grid-cols-4">
					{rows.map((row, index) => {
						const url = String(row[column] ?? "");
						return (
							<li key={url || index} className="group relative aspect-square overflow-hidden rounded-2xl bg-zinc-100">
								<a href={url} target="_blank" rel="noreferrer">
									<img src={url} alt="" className="size-full object-cover" loading="lazy" />
								</a>
								{!disabled && (
									<button
										type="button"
										onClick={() => onChange(rows.filter((_, i) => i !== index))}
										className="absolute right-1.5 top-1.5 grid size-7 place-items-center rounded-full bg-zinc-950/60 text-white backdrop-blur"
										aria-label="Remove photo"
									>
										<X className="size-4" />
									</button>
								)}
							</li>
						);
					})}
					{Array.from({ length: uploading }, (_, i) => (
						<li key={`up-${i}`} className="grid aspect-square place-items-center rounded-2xl bg-zinc-100">
							<Loader2 className="size-5 animate-spin text-muted" aria-label="Uploading" />
						</li>
					))}
					{!disabled && (
						<li>
							<button
								type="button"
								onClick={() => input.current?.click()}
								className="flex aspect-square w-full flex-col items-center justify-center gap-1 rounded-2xl border-2 border-dashed border-zinc-200 text-muted transition hover:border-zinc-400 hover:text-ink"
							>
								<Plus className="size-6" strokeWidth={1.75} />
								<span className="text-xs font-medium">Add photo</span>
							</button>
						</li>
					)}
				</ul>
			) : (
				<ul className="divide-y divide-line">
					{rows.map((row, index) => {
						const url = String(row[column] ?? "");
						return (
							<li key={url || index} className="flex items-center gap-3 py-2.5">
								<FileText className="size-5 shrink-0 text-muted" strokeWidth={1.75} />
								<a href={url} target="_blank" rel="noreferrer" className="min-w-0 flex-1 truncate text-[15px] hover:text-brand-500">
									{String(row.caption ?? "") || url.split("/").pop()}
								</a>
								{!disabled && (
									<button type="button" onClick={() => onChange(rows.filter((_, i) => i !== index))} className="text-muted hover:text-ink" aria-label="Remove file">
										<X className="size-4" />
									</button>
								)}
							</li>
						);
					})}
					{uploading > 0 && (
						<li className="flex items-center gap-3 py-2.5 text-muted">
							<Loader2 className="size-5 animate-spin" /> Uploading…
						</li>
					)}
					{!disabled && (
						<li className="pt-2">
							<button type="button" onClick={() => input.current?.click()} className="inline-flex items-center gap-1.5 text-[15px] font-medium text-brand-500">
								<Plus className="size-4" /> Add file
							</button>
						</li>
					)}
				</ul>
			)}

			<input
				ref={input}
				type="file"
				accept={photos ? "image/*" : undefined}
				multiple
				hidden
				onChange={(e) => {
					if (e.target.files) void add(e.target.files);
					e.target.value = "";
				}}
			/>
			{error && <p className="mt-2 text-sm text-red-600">{error}</p>}
			{(minimum > 1 || !disabled) && photos && (
				<p className={`mt-2 text-[13px] ${minimum && count < minimum ? "text-amber-600" : "text-muted"}`}>
					{minimum ? `${count} of ${minimum} minimum` : `${count} photo${count === 1 ? "" : "s"}`}
					{!disabled && " · drop photos here on a computer"}
				</p>
			)}
		</div>
	);
}
