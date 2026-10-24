// PDF rendering for reference documents (#42), with pdf.js. The library and its worker are loaded
// only when a document is first shown, so checklists without references stay light. The legacy
// build is used on purpose: the modern one needs very recent JavaScript (e.g. Map.getOrInsertComputed)
// that technicians' phones and current Chromium do not have yet.

import type { PDFDocumentProxy } from "pdfjs-dist";

const documents = new Map<string, Promise<PDFDocumentProxy>>();

async function pdfjs() {
	const [lib, worker] = await Promise.all([
		import("pdfjs-dist/legacy/build/pdf.mjs"),
		import("pdfjs-dist/legacy/build/pdf.worker.min.mjs?url"),
	]);
	lib.GlobalWorkerOptions.workerSrc = worker.default;
	return lib;
}

export function isPdf(url: string): boolean {
	return url.toLowerCase().split("?")[0].endsWith(".pdf");
}

/** The document at `url` (a private file: the session cookie is sent), loaded once per page view. */
export function loadPdf(url: string): Promise<PDFDocumentProxy> {
	let pending = documents.get(url);
	if (!pending) {
		pending = pdfjs().then((lib) => lib.getDocument({ url, withCredentials: true }).promise);
		pending.catch(() => documents.delete(url)); // let a later attempt retry
		documents.set(url, pending);
	}
	return pending;
}

/** Start drawing one page into `canvas`, scaled to `width` CSS pixels (sharp on high-density
 * screens). Returns the running task: await `task.promise`, or `task.cancel()` it. */
export async function renderPage(doc: PDFDocumentProxy, number: number, canvas: HTMLCanvasElement, width: number) {
	const page = await doc.getPage(number);
	const ratio = window.devicePixelRatio || 1;
	const viewport = page.getViewport({ scale: (width / page.getViewport({ scale: 1 }).width) * ratio });
	canvas.width = Math.floor(viewport.width);
	canvas.height = Math.floor(viewport.height);
	canvas.style.width = `${width}px`;
	canvas.style.height = `${viewport.height / ratio}px`;
	return page.render({ canvas, viewport });
}
