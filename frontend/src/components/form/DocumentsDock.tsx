// The checklist's documents, out of the way but easy to find: a "Documents" button at the bottom right
// that opens a side panel where each one can be read or downloaded. The steps that need a document
// still show it in place.

import { BookOpen, Download, FileText, X } from "lucide-react";
import { useEffect, useState } from "react";

import { uniqueDocuments } from "../../lib/references";
import type { Reference, Section } from "../../lib/types";
import { PdfViewer } from "./PdfViewer";
import { usePdfPreview } from "./usePdfPreview";

/** `raised` lifts the button above the form's Submit bar. */
export function DocumentsDock({ references, sections, raised = false }: { references: Reference[]; sections: Section[]; raised?: boolean }) {
	const [open, setOpen] = useState(false);

	useEffect(() => {
		if (!open) return;
		const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
		window.addEventListener("keydown", onKey);
		return () => window.removeEventListener("keydown", onKey);
	}, [open]);

	const documents = uniqueDocuments(references, sections);
	if (!documents.length) return null;

	return (
		<>
			{!open && (
				<button
					type="button"
					onClick={() => setOpen(true)}
					className={`fixed right-4 z-30 inline-flex h-14 items-center gap-3 rounded-full bg-brand-500 pl-4 pr-3 text-white shadow-xl shadow-blue-600/30 ring-4 ring-white transition hover:-translate-y-0.5 hover:bg-brand-600 active:scale-95 sm:right-6 ${
						raised ? "bottom-28" : "bottom-6"
					}`}
					aria-label={`Documents for this checklist (${documents.length})`}
					aria-expanded={false}
					aria-controls="documents-panel"
				>
					<BookOpen className="size-5" aria-hidden />
					<span className="text-[15px] font-semibold">Documents</span>
					<span className="grid h-7 min-w-7 place-items-center rounded-full bg-white px-1.5 text-sm font-bold text-brand-600">{documents.length}</span>
				</button>
			)}

			{open && <div className="fixed inset-0 z-40 bg-slate-950/20 lg:hidden" onClick={() => setOpen(false)} aria-hidden />}
			<aside
				id="documents-panel"
				aria-label="Documents for this checklist"
				aria-hidden={!open}
				inert={!open}
				className={`fixed bottom-0 right-0 top-(--shell-top) z-40 flex w-full max-w-md flex-col border-l border-slate-200 bg-slate-50 shadow-2xl transition-transform duration-200 ${
					open ? "translate-x-0" : "translate-x-full"
				}`}
			>
				<div className="flex items-center gap-3 border-b border-slate-200 bg-white px-5 py-4">
					<span className="grid size-10 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-600">
						<BookOpen className="size-5" aria-hidden />
					</span>
					<div className="min-w-0 flex-1">
						<h2 className="font-semibold text-slate-900">Documents</h2>
						<p className="text-[13px] text-slate-500">
							{documents.length} for this checklist · also shown in the steps
						</p>
					</div>
					<button
						type="button"
						onClick={() => setOpen(false)}
						className="grid size-9 shrink-0 place-items-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-900"
						aria-label="Close documents"
					>
						<X className="size-5" />
					</button>
				</div>
				{open && (
					<ul className="flex-1 space-y-3 overflow-y-auto p-4">
						{documents.map(({ reference, places }) => (
							<DocumentItem key={reference.url} reference={reference} places={places} />
						))}
					</ul>
				)}
			</aside>
		</>
	);
}

const THUMB_WIDTH = 48;

/** One document in the panel: tap the card to read it; a quiet icon in the corner downloads it. */
function DocumentItem({ reference, places }: { reference: Reference; places: string[] }) {
	const { pdf, target, thumb, failed, kind } = usePdfPreview<HTMLLIElement>(reference.url, THUMB_WIDTH);
	const [reading, setReading] = useState(false);

	return (
		<li ref={target} className="relative">
			<button
				type="button"
				onClick={() => setReading(true)}
				className="group block w-full rounded-2xl bg-white p-4 pr-12 text-left shadow-xs ring-1 ring-slate-200 transition hover:ring-brand-500 active:scale-[0.99]"
				aria-label={`Read ${reference.title}`}
			>
				<span className="flex gap-3">
					<span className="grid h-16 w-12 shrink-0 place-items-center overflow-hidden rounded-md bg-slate-100 ring-1 ring-slate-200">
						{pdf && !failed ? (
							<canvas ref={thumb} aria-hidden />
						) : !pdf ? (
							<img src={reference.url} alt="" className="size-full object-cover" loading="lazy" />
						) : (
							<FileText className="size-5 text-slate-400" aria-hidden />
						)}
					</span>
					<span className="min-w-0 flex-1">
						<span className="line-clamp-2 font-medium leading-snug text-slate-900 group-hover:text-brand-600" title={reference.title}>
							{reference.title}
						</span>
						<span className="mt-0.5 block text-[13px] text-slate-500">{kind}</span>
					</span>
				</span>
				{places.length > 0 && (
					<span className="mt-3 flex flex-wrap gap-1.5">
						{places.map((place) => (
							<span key={place} className="max-w-full truncate rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
								{place}
							</span>
						))}
					</span>
				)}
			</button>
			<a
				href={reference.url}
				download
				className="absolute right-2 top-2 grid size-9 place-items-center rounded-lg text-slate-400 transition hover:bg-slate-100 hover:text-brand-600"
				aria-label={`Download ${reference.title}`}
				title="Download"
			>
				<Download className="size-[18px]" aria-hidden />
			</a>
			{reading && <PdfViewer reference={reference} onClose={() => setReading(false)} />}
		</li>
	);
}
