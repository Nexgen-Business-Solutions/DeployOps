import { ChevronDown, House, KeyRound, LayoutGrid, LogOut } from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { Link } from "react-router";

import { initials } from "../lib/format";
import { useSession } from "../lib/session";

/** Avatar button with a dropdown: account details, links and log out. Closes on outside click or Escape. */
export function UserMenu({ onLogout }: { onLogout: () => void }) {
	const me = useSession();
	const [open, setOpen] = useState(false);
	const root = useRef<HTMLDivElement>(null);

	useEffect(() => {
		if (!open) return;
		const onPointer = (event: PointerEvent) => {
			if (!root.current?.contains(event.target as Node)) setOpen(false);
		};
		const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
		document.addEventListener("pointerdown", onPointer);
		document.addEventListener("keydown", onKey);
		return () => {
			document.removeEventListener("pointerdown", onPointer);
			document.removeEventListener("keydown", onKey);
		};
	}, [open]);

	const close = () => setOpen(false);

	return (
		<div ref={root} className="relative">
			<button
				type="button"
				onClick={() => setOpen(!open)}
				aria-haspopup="menu"
				aria-expanded={open}
				className="flex items-center gap-1.5 rounded-full p-1 pr-2 transition hover:bg-zinc-100"
			>
				<span className="grid size-8 place-items-center rounded-full bg-brand-500 text-xs font-semibold text-white">{initials(me.full_name)}</span>
				<ChevronDown className={`size-4 text-muted transition ${open ? "rotate-180" : ""}`} aria-hidden />
			</button>

			{open && (
				<div role="menu" className="absolute right-0 top-full z-40 mt-2 w-64 origin-top-right rounded-2xl bg-white p-1.5 shadow-xl ring-1 ring-zinc-200">
					<div className="px-3 pb-3 pt-2">
						<p className="truncate font-medium">{me.full_name}</p>
						<p className="truncate text-[13px] text-muted">{me.user}</p>
						<p className="mt-2 flex flex-wrap gap-1">
							{me.roles.map((role) => (
								<span key={role} className="rounded-full bg-zinc-100 px-2 py-0.5 text-[11px] font-medium text-zinc-600">
									{role}
								</span>
							))}
						</p>
					</div>
					<div className="border-t border-line py-1">
						<Item to="/" icon={<House className="size-4" />} onClick={close}>
							My checklists
						</Item>
						{me.has_desk && (
							<Item href="/desk/deployops" icon={<LayoutGrid className="size-4" />}>
								Open Desk
							</Item>
						)}
						<Item to="/password" icon={<KeyRound className="size-4" />} onClick={close}>
							Change password
						</Item>
					</div>
					<div className="border-t border-line pt-1">
						<button
							type="button"
							role="menuitem"
							onClick={onLogout}
							className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm text-red-600 hover:bg-red-50"
						>
							<LogOut className="size-4" /> Log out
						</button>
					</div>
				</div>
			)}
		</div>
	);
}

function Item({ to, href, icon, children, onClick }: { to?: string; href?: string; icon: ReactNode; children: ReactNode; onClick?: () => void }) {
	const className = "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-ink hover:bg-zinc-100";
	return to ? (
		<Link to={to} role="menuitem" className={className} onClick={onClick}>
			<span className="text-muted">{icon}</span>
			{children}
		</Link>
	) : (
		<a href={href} role="menuitem" className={className}>
			<span className="text-muted">{icon}</span>
			{children}
		</a>
	);
}
