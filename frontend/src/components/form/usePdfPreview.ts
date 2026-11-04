import { useEffect, useRef, useState } from "react";

import { isPdf, loadPdf, renderPage } from "../../lib/pdf";

/**
 * A reference's first-page thumbnail and page count, rendered once its element scrolls into view so
 * long checklists stay fast. Attach `target` to the visible element and `thumb` to a canvas.
 */
export function usePdfPreview<T extends HTMLElement>(url: string, width: number) {
	const pdf = isPdf(url);
	const target = useRef<T>(null);
	const thumb = useRef<HTMLCanvasElement>(null);
	const [pages, setPages] = useState<number | null>(null);
	const [failed, setFailed] = useState(false);

	useEffect(() => {
		const element = target.current;
		if (!pdf || !element) return;
		let live = true;
		const observer = new IntersectionObserver((entries) => {
			if (!entries.some((entry) => entry.isIntersecting)) return;
			observer.disconnect();
			loadPdf(url)
				.then(async (doc) => {
					if (!live) return;
					setPages(doc.numPages);
					if (thumb.current) await (await renderPage(doc, 1, thumb.current, width)).promise;
				})
				.catch((error) => {
					console.warn("Reference preview failed", url, error);
					if (live) setFailed(true);
				});
		});
		observer.observe(element);
		return () => {
			live = false;
			observer.disconnect();
		};
	}, [pdf, url, width]);

	const kind = pdf ? (pages ? `PDF · ${pages} page${pages === 1 ? "" : "s"}` : "PDF") : "Image";
	return { pdf, target, thumb, pages, failed, kind };
}
