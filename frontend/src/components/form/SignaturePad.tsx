import { RotateCcw } from "lucide-react";
import { type PointerEvent, useEffect, useRef, useState } from "react";

/** Finger or mouse signature; stored on the form as a PNG data URL (Frappe Signature field). */
export function SignaturePad({ value, disabled, onChange }: { value: string | null; disabled: boolean; onChange: (value: string | null) => void }) {
	const canvas = useRef<HTMLCanvasElement>(null);
	const drawing = useRef(false);
	const dirty = useRef(false);
	const [editing, setEditing] = useState(false);
	const showPad = !disabled && (!value || editing);

	useEffect(() => {
		const element = canvas.current;
		if (!element || !showPad) return;
		const ratio = window.devicePixelRatio || 1;
		const rect = element.getBoundingClientRect();
		element.width = rect.width * ratio;
		element.height = rect.height * ratio;
		const context = element.getContext("2d");
		if (!context) return;
		context.scale(ratio, ratio);
		context.lineWidth = 2.2;
		context.lineCap = "round";
		context.lineJoin = "round";
		context.strokeStyle = "#09090b";
	}, [showPad]);

	function point(event: PointerEvent<HTMLCanvasElement>) {
		const rect = event.currentTarget.getBoundingClientRect();
		return { x: event.clientX - rect.left, y: event.clientY - rect.top };
	}

	function start(event: PointerEvent<HTMLCanvasElement>) {
		event.currentTarget.setPointerCapture(event.pointerId);
		const context = event.currentTarget.getContext("2d");
		const { x, y } = point(event);
		context?.beginPath();
		context?.moveTo(x, y);
		drawing.current = true;
	}

	function move(event: PointerEvent<HTMLCanvasElement>) {
		if (!drawing.current) return;
		const context = event.currentTarget.getContext("2d");
		const { x, y } = point(event);
		context?.lineTo(x, y);
		context?.stroke();
		dirty.current = true;
	}

	function end() {
		if (!drawing.current) return;
		drawing.current = false;
		if (canvas.current && dirty.current) onChange(canvas.current.toDataURL("image/png"));
	}

	function clear() {
		const element = canvas.current;
		element?.getContext("2d")?.clearRect(0, 0, element.width, element.height);
		dirty.current = false;
		setEditing(true);
		onChange(null);
	}

	if (!showPad) {
		return value ? (
			<div className="flex items-end justify-between gap-3 rounded-2xl bg-zinc-50 p-3">
				<img src={value} alt="Signature" className="h-28 max-w-full object-contain" />
				{!disabled && (
					<button type="button" onClick={clear} className="inline-flex items-center gap-1.5 text-sm font-medium text-muted hover:text-ink">
						<RotateCcw className="size-4" aria-hidden /> Redo
					</button>
				)}
			</div>
		) : (
			<p className="text-[15px] text-zinc-400">Not signed</p>
		);
	}

	return (
		<div>
			<div className="relative rounded-2xl bg-zinc-50">
				<canvas
					ref={canvas}
					className="block h-40 w-full touch-none rounded-2xl"
					onPointerDown={start}
					onPointerMove={move}
					onPointerUp={end}
					onPointerLeave={end}
					aria-label="Signature pad"
				/>
				<span className="pointer-events-none absolute bottom-8 left-6 right-6 border-t border-zinc-300" />
				<span className="pointer-events-none absolute bottom-3 left-6 text-xs text-zinc-400">Sign above the line</span>
			</div>
			{value && (
				<button type="button" onClick={clear} className="mt-2 inline-flex items-center gap-1.5 text-sm font-medium text-muted hover:text-ink">
					<RotateCcw className="size-4" aria-hidden /> Clear
				</button>
			)}
		</div>
	);
}
