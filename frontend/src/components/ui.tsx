// Small shared UI kit, "clean mono": white, near-black type, hairlines, blue for actions only.

import { ChevronLeft, Loader2 } from "lucide-react";
import { type ButtonHTMLAttributes, type ReactNode, useEffect, useState } from "react";
import { Link } from "react-router";

type Variant = "primary" | "secondary" | "danger" | "ghost";

const VARIANTS: Record<Variant, string> = {
	primary: "bg-brand-500 text-white hover:bg-brand-600",
	secondary: "bg-zinc-100 text-ink hover:bg-zinc-200",
	danger: "bg-red-50 text-red-600 hover:bg-red-100",
	ghost: "text-ink hover:bg-zinc-100",
};

export function Button({
	variant = "primary",
	loading = false,
	icon,
	className = "",
	children,
	disabled,
	...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean; icon?: ReactNode }) {
	return (
		<button
			{...props}
			disabled={disabled || loading}
			className={`inline-flex h-12 items-center justify-center gap-2 rounded-full px-6 text-[15px] font-medium transition active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${className}`}
		>
			{loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : icon}
			{children}
		</button>
	);
}

/** The DeployOps mark: a blue rounded square with a white "D" stroke. */
export function Logo({ size = 36 }: { size?: number }) {
	return (
		<svg width={size} height={size} viewBox="0 0 40 40" aria-hidden className="shrink-0">
			<rect width="40" height="40" rx="11" fill="#2b7fff" />
			<path d="M14 11h6.5a9 9 0 0 1 0 18H14z" fill="none" stroke="#fff" strokeWidth="3.2" strokeLinejoin="round" />
			<circle cx="20.5" cy="20" r="2.4" fill="#fff" />
		</svg>
	);
}

export function TopBar({ title, back, right }: { title?: string; back?: string; right?: ReactNode }) {
	return (
		<header className="sticky top-0 z-20 bg-white/85 backdrop-blur-xl">
			<div className="mx-auto flex h-14 max-w-[52rem] items-center gap-1 px-2 sm:px-4">
				{back ? (
					<Link to={back} className="grid size-10 place-items-center rounded-full hover:bg-zinc-100" aria-label="Back">
						<ChevronLeft className="size-6" />
					</Link>
				) : (
					<span className="pl-2">
						<Logo size={30} />
					</span>
				)}
				<h1 className="min-w-0 flex-1 truncate px-1 text-[15px] font-semibold">{title}</h1>
				{right}
			</div>
		</header>
	);
}

export function Page({ children, className = "" }: { children: ReactNode; className?: string }) {
	return <main className={`mx-auto max-w-[52rem] px-5 pb-16 pt-4 sm:px-6 ${className}`}>{children}</main>;
}

export function Banner({ kind = "error", children }: { kind?: "error" | "info" | "success" | "warning"; children: ReactNode }) {
	const styles = {
		error: "bg-red-50 text-red-700",
		info: "bg-brand-50 text-blue-800",
		success: "bg-emerald-50 text-emerald-800",
		warning: "bg-amber-50 text-amber-900",
	}[kind];
	return (
		<div className={`whitespace-pre-line rounded-2xl px-4 py-3 text-sm ${styles}`} role={kind === "error" ? "alert" : "status"}>
			{children}
		</div>
	);
}

const DOTS: Record<string, string> = {
	Draft: "bg-zinc-300",
	Pending: "bg-zinc-300",
	"In Preparation": "bg-brand-500",
	"Ready for Deployment": "bg-brand-500",
	"On Site": "bg-brand-500",
	"In Progress": "bg-brand-500",
	"Pending Review": "bg-amber-500",
	"Returned for Correction": "bg-amber-500",
	Blocked: "bg-red-500",
	Done: "bg-emerald-500",
	Completed: "bg-emerald-500",
	Cancelled: "bg-zinc-300",
};

export function Status({ status }: { status: string }) {
	return (
		<span className="inline-flex shrink-0 items-center gap-1.5 text-[13px] text-muted">
			<span className={`size-1.5 rounded-full ${DOTS[status] ?? "bg-zinc-300"}`} />
			{status}
		</span>
	);
}

export function Skeleton({ className = "" }: { className?: string }) {
	return <div className={`animate-pulse rounded-2xl bg-zinc-100 ${className}`} />;
}

export function Empty({ title, text }: { title: string; text?: string }) {
	return (
		<div className="py-16 text-center">
			<p className="font-medium">{title}</p>
			{text && <p className="mt-1 text-sm text-muted">{text}</p>}
		</div>
	);
}

/** Bottom sheet on phones, centred dialog on larger screens. */
export function Dialog({ open, title, children, onClose }: { open: boolean; title: string; children: ReactNode; onClose: () => void }) {
	useEffect(() => {
		if (!open) return;
		const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
		window.addEventListener("keydown", onKey);
		return () => window.removeEventListener("keydown", onKey);
	}, [open, onClose]);
	if (!open) return null;
	return (
		<div className="fixed inset-0 z-50 flex items-end justify-center bg-zinc-950/30 backdrop-blur-[2px] sm:items-center" onClick={onClose}>
			<div
				role="dialog"
				aria-modal="true"
				aria-label={title}
				className="w-full max-w-md rounded-t-[28px] bg-white px-6 pb-[max(env(safe-area-inset-bottom),1.5rem)] pt-6 sm:rounded-[28px]"
				onClick={(e) => e.stopPropagation()}
			>
				<h2 className="mb-4 text-xl font-semibold tracking-tight">{title}</h2>
				{children}
			</div>
		</div>
	);
}

/** Ask for a reason (block, return, cancel…) or a plain confirmation. */
export function ActionDialog({
	open,
	title,
	needsReason,
	warning,
	confirmLabel,
	busy,
	error,
	onConfirm,
	onClose,
}: {
	open: boolean;
	title: string;
	needsReason: boolean;
	warning?: string;
	confirmLabel: string;
	busy: boolean;
	error: string | null;
	onConfirm: (reason: string) => void;
	onClose: () => void;
}) {
	const [reason, setReason] = useState("");
	return (
		<Dialog open={open} title={title} onClose={onClose}>
			{warning && <p className="mb-4 text-[15px] text-muted">{warning}</p>}
			{needsReason && (
				<label className="mb-4 block">
					<span className="mb-1.5 block text-sm font-medium">Reason</span>
					<textarea className="field-input min-h-24" value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
				</label>
			)}
			{error && (
				<div className="mb-4">
					<Banner>{error}</Banner>
				</div>
			)}
			<div className="grid grid-cols-2 gap-3">
				<Button variant="secondary" onClick={onClose} type="button">
					Back
				</Button>
				<Button
					loading={busy}
					disabled={needsReason && !reason.trim()}
					onClick={() => {
						onConfirm(reason.trim());
						setReason("");
					}}
					type="button"
				>
					{confirmLabel}
				</Button>
			</div>
		</Dialog>
	);
}
