import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";
import { ChevronLeft, ChevronRight, Download, Loader2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { isPdf, loadPdf, renderPage } from "../../lib/pdf";
import type { Reference } from "../../lib/types";

/** Full-screen, page-by-page viewer for a reference document; images are shown as they are. */
export function PdfViewer({ reference, onClose }: { reference: Reference; onClose: () => void }) {
	const pdf = isPdf(reference.url);
	const [doc, setDoc] = useState<PDFDocumentProxy | null>(null);
	const [page, setPage] = useState(1);
	const [error, setError] = useState(false);
	const [rendering, setRendering] = useState(pdf);
	const canvas = useRef<HTMLCanvasElement>(null);
	const body = useRef<HTMLDivElement>(null);
	const pages = doc?.numPages ?? 0;

	useEffect(() => {
		if (!pdf) return;
		let live = true;
		loadPdf(reference.url).then(
			(loaded) => live && setDoc(loaded),
			() => live && setError(true),
		);
		return () => {
			live = false;
		};
	}, [pdf, reference.url]);

	useEffect(() => {
		const element = canvas.current;
		const container = body.current;
		if (!doc || !element || !container) return;
		let task: RenderTask | null = null;
		let latest = 0;
		let live = true;
		const draw = () => {
			const id = ++latest;
			task?.cancel();
			setRendering(true);
			const width = Math.min(container.clientWidth - 32, 900);
			renderPage(doc, page, element, width)
				.then((started) => {
					if (id !== latest || !live) {
						started.promise.catch(() => undefined); // overtaken by a newer draw (page turned, resized)
						started.cancel();
						return;
					}
					task = started;
					return started.promise;
				})
				.catch((error) => {
					// A cancelled render (page turned, resized) is expected; anything else is logged.
					if (error?.name !== "RenderingCancelledException") console.warn("Page render failed", error);
				})
				.finally(() => live && id === latest && setRendering(false));
		};
		draw();
		container.scrollTo({ top: 0 });
		const resize = new ResizeObserver(() => draw());
		resize.observe(container);
		return () => {
			live = false;
			task?.cancel();
			resize.disconnect();
		};
	}, [doc, page]);

	useEffect(() => {
		const onKey = (e: KeyboardEvent) => {
			if (e.key === "Escape") onClose();
			if (e.key === "ArrowRight") setPage((p) => Math.min(p + 1, pages || p));
			if (e.key === "ArrowLeft") setPage((p) => Math.max(p - 1, 1));
		};
		const overflow = document.body.style.overflow;
		document.body.style.overflow = "hidden";
		window.addEventListener("keydown", onKey);
		return () => {
			document.body.style.overflow = overflow;
			window.removeEventListener("keydown", onKey);
		};
	}, [onClose, pages]);

	return (
		<div role="dialog" aria-modal="true" aria-label={reference.title} className="fixed inset-0 z-50 flex flex-col bg-zinc-950 text-white">
			<header className="flex h-14 shrink-0 items-center gap-2 px-2 sm:px-4">
				<button type="button" onClick={onClose} className="grid size-10 place-items-center rounded-full hover:bg-white/10" aria-label="Close">
					<X className="size-5" />
				</button>
				<h2 className="min-w-0 flex-1 truncate text-[15px] font-medium">{reference.title}</h2>
				{pages > 1 && (
					<div className="flex items-center gap-1 text-sm tabular-nums">
						<button
							type="button"
							onClick={() => setPage((p) => Math.max(p - 1, 1))}
							disabled={page <= 1}
							className="grid size-9 place-items-center rounded-full hover:bg-white/10 disabled:opacity-30"
							aria-label="Previous page"
						>
							<ChevronLeft className="size-5" />
						</button>
						<span>
							{page} / {pages}
						</span>
						<button
							type="button"
							onClick={() => setPage((p) => Math.min(p + 1, pages))}
							disabled={page >= pages}
							className="grid size-9 place-items-center rounded-full hover:bg-white/10 disabled:opacity-30"
							aria-label="Next page"
						>
							<ChevronRight className="size-5" />
						</button>
					</div>
				)}
				<a href={reference.url} download className="grid size-10 place-items-center rounded-full hover:bg-white/10" aria-label="Download">
					<Download className="size-5" />
				</a>
			</header>

			<div ref={body} className="relative flex-1 overflow-auto px-4 pb-8">
				{error ? (
					<p className="mt-16 text-center text-sm text-zinc-300">
						This document could not be shown.{" "}
						<a href={reference.url} target="_blank" rel="noreferrer" className="underline">
							Open it in a new tab
						</a>
						.
					</p>
				) : pdf ? (
					<>
						<canvas ref={canvas} className="mx-auto block rounded bg-white shadow-2xl" />
						{rendering && <Loader2 className="absolute left-1/2 top-16 size-6 -translate-x-1/2 animate-spin text-zinc-400" aria-label="Loading page" />}
					</>
				) : (
					<img src={reference.url} alt={reference.title} className="mx-auto max-h-full rounded bg-white" />
				)}
			</div>
		</div>
	);
}
