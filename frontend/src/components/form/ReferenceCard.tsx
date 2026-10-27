import { ArrowRight, FileText } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { isPdf, loadPdf, renderPage } from "../../lib/pdf";
import type { Reference } from "../../lib/types";
import { PdfViewer } from "./PdfViewer";

const THUMB_WIDTH = 56;

/** A reference document as a card: first-page preview, title, page count and a Read button. */
export function ReferenceCard({ reference, note }: { reference: Reference; note?: string }) {
	const pdf = isPdf(reference.url);
	const card = useRef<HTMLButtonElement>(null);
	const thumb = useRef<HTMLCanvasElement>(null);
	const [pages, setPages] = useState<number | null>(null);
	const [failed, setFailed] = useState(false);
	const [open, setOpen] = useState(false);

	// Render the first page once the card scrolls into view, so long checklists stay fast.
	useEffect(() => {
		const element = card.current;
		if (!pdf || !element) return;
		let live = true;
		const observer = new IntersectionObserver((entries) => {
			if (!entries.some((entry) => entry.isIntersecting)) return;
			observer.disconnect();
			loadPdf(reference.url)
				.then(async (doc) => {
					if (!live) return;
					setPages(doc.numPages);
					if (thumb.current) await (await renderPage(doc, 1, thumb.current, THUMB_WIDTH)).promise;
				})
				.catch((error) => {
					console.warn("Reference preview failed", reference.url, error);
					if (live) setFailed(true);
				});
		});
		observer.observe(element);
		return () => {
			live = false;
			observer.disconnect();
		};
	}, [pdf, reference.url]);

	return (
		<>
			<button
				ref={card}
				type="button"
				onClick={() => setOpen(true)}
				className="group flex w-full items-center gap-4 rounded-2xl bg-white p-3 text-left ring-1 ring-line transition hover:ring-brand-500 active:scale-[0.99]"
			>
				<span className="grid h-[72px] w-14 shrink-0 place-items-center overflow-hidden rounded-lg bg-zinc-100 ring-1 ring-zinc-200">
					{pdf && !failed ? (
						<canvas ref={thumb} aria-hidden />
					) : !pdf ? (
						<img src={reference.url} alt="" className="size-full object-cover" loading="lazy" />
					) : (
						<FileText className="size-6 text-zinc-400" aria-hidden />
					)}
				</span>
				<span className="min-w-0 flex-1">
					<span className="block font-medium leading-snug">{reference.title}</span>
					<span className="mt-0.5 block text-[13px] text-muted">
						{pdf ? (pages ? `PDF · ${pages} page${pages === 1 ? "" : "s"}` : "PDF") : "Image"}
						{note ? ` · ${note}` : ""}
					</span>
				</span>
				<span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-brand-500 px-3.5 py-2 text-sm font-medium text-white transition group-hover:bg-brand-600">
					Read <ArrowRight className="size-4" aria-hidden />
				</span>
			</button>
			{open && <PdfViewer reference={reference} onClose={() => setOpen(false)} />}
		</>
	);
}
