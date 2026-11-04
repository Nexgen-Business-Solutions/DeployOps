// The header and sidebar around every screen, in the look of the TrixaPOS suite apps. With the suite
// (trixapos_core installed) it also holds the landing screen, Overview; standalone, the home grid stays
// full page and the sidebar's first link goes back to it. On phones and tablets the sidebar is a drawer
// behind the menu button.

import { House, LayoutDashboard, Menu, RefreshCw, X } from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router";

import { CardIcon } from "./CardIcon";
import { CARD_COLORS, DEFAULT_COLOR } from "../lib/cards";
import { ShellContext } from "../lib/shell";
import type { Card } from "../lib/types";
import { useApi } from "../lib/useApi";
import { Logo, Skeleton } from "./ui";
import { UserMenu } from "./UserMenu";

export default function AppShell({ suite, onLogout }: { suite: boolean; onLogout: () => void }) {
	const { data: cards, error, loading, reload } = useApi<Card[]>("deployops.api.technician.home");
	const [menuOpen, setMenuOpen] = useState(false);
	const [refreshKey, setRefreshKey] = useState(0);
	const { pathname } = useLocation();
	const shownPath = useRef(pathname);

	// Counts change as jobs move on: reload them when the screen changes, and close the drawer.
	useEffect(() => {
		if (shownPath.current === pathname) return;
		shownPath.current = pathname;
		setMenuOpen(false);
		void reload();
	}, [pathname, reload]);

	useEffect(() => {
		if (!menuOpen) return;
		const onKey = (event: KeyboardEvent) => event.key === "Escape" && setMenuOpen(false);
		window.addEventListener("keydown", onKey);
		return () => window.removeEventListener("keydown", onKey);
	}, [menuOpen]);

	function refresh() {
		setRefreshKey((key) => key + 1); // remounts the screen, which reloads its data
		void reload();
	}

	return (
		<ShellContext.Provider value={{ cards, error, loading }}>
			<div className="app-shell min-h-svh bg-slate-50">
				<header className="sticky top-0 z-30 flex h-16 items-center gap-2 border-b border-slate-200 bg-white px-3 sm:px-5">
					<button
						type="button"
						onClick={() => setMenuOpen(true)}
						className="grid size-10 place-items-center rounded-lg text-slate-700 hover:bg-slate-100 lg:hidden"
						aria-label="Open menu"
						aria-expanded={menuOpen}
						aria-controls="app-sidebar"
					>
						<Menu className="size-5" />
					</button>
					<Logo size={28} />
					<h1 className="min-w-0 flex-1 truncate pl-1 text-lg font-semibold tracking-tight text-slate-900">Deployments</h1>
					<button
						type="button"
						onClick={refresh}
						className="inline-flex h-10 items-center gap-2 rounded-lg bg-slate-700 px-3 text-sm font-medium text-white transition hover:bg-slate-800 active:scale-[0.98] sm:px-4"
					>
						<RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} aria-hidden />
						<span className="hidden sm:inline">Refresh</span>
						<span className="sr-only sm:hidden">Refresh</span>
					</button>
					<UserMenu onLogout={onLogout} />
				</header>

				{menuOpen && (
					<div className="fixed inset-0 z-40 bg-slate-950/30 backdrop-blur-[2px] lg:hidden" onClick={() => setMenuOpen(false)} aria-hidden />
				)}
				<aside
					id="app-sidebar"
					className={`fixed inset-y-0 left-0 z-50 flex w-72 flex-col overflow-y-auto border-r border-slate-200 bg-white px-3 pb-6 pt-3 transition-transform duration-200 lg:top-16 lg:z-20 lg:w-64 lg:translate-x-0 ${
						menuOpen ? "translate-x-0 shadow-2xl" : "-translate-x-full"
					}`}
					aria-label="DeployOps"
				>
					<div className="mb-3 flex items-center justify-between px-2 lg:hidden">
						<span className="flex items-center gap-2 font-semibold text-slate-900">
							<Logo size={26} /> Deployments
						</span>
						<button
							type="button"
							onClick={() => setMenuOpen(false)}
							className="grid size-10 place-items-center rounded-lg text-slate-600 hover:bg-slate-100"
							aria-label="Close menu"
						>
							<X className="size-5" />
						</button>
					</div>
					<Sidebar suite={suite} cards={cards} loading={loading} />
				</aside>

				<div className="lg:pl-64">
					<Outlet key={refreshKey} />
				</div>
			</div>
		</ShellContext.Provider>
	);
}

function Sidebar({ suite, cards, loading }: { suite: boolean; cards: Card[] | null; loading: boolean }) {
	return (
		<nav className="flex flex-col gap-1 lg:pt-4">
			{suite ? (
				<Item to="/" end icon={<LayoutDashboard className="size-[18px]" />}>
					Overview
				</Item>
			) : (
				<Item to="/" end icon={<House className="size-[18px]" />}>
					Home
				</Item>
			)}

			<p className="mt-7 px-4 pb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">Checklists</p>
			{loading && !cards
				? Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="mx-2 my-1 h-8 rounded-lg" />)
				: cards?.map((card) => {
						return (
							<Item
								key={card.id}
								to={`/c/${card.id}`}
								icon={
									<span className={`grid size-7 place-items-center rounded-lg ring-1 ${CARD_COLORS[card.id] ?? DEFAULT_COLOR}`}>
										<CardIcon card={card} className="size-4" strokeWidth={1.75} />
									</span>
								}
								badge={card.open_jobs}
								attention={card.attention > 0}
							>
								{card.title}
							</Item>
						);
					})}
		</nav>
	);
}

function Item({
	to,
	end,
	icon,
	badge,
	attention,
	children,
}: {
	to: string;
	end?: boolean;
	icon: ReactNode;
	badge?: number;
	attention?: boolean;
	children: ReactNode;
}) {
	return (
		<NavLink
			to={to}
			end={end}
			className={({ isActive }) =>
				`flex min-h-11 items-center gap-3 rounded-xl px-4 py-2 text-[15px] font-medium transition ${
					isActive
						? "bg-gradient-to-r from-blue-600 to-blue-700 text-white shadow-md shadow-blue-600/25 [&_.badge]:bg-white/20 [&_.badge]:text-white"
						: "text-slate-700 hover:bg-slate-100"
				}`
			}
		>
			{icon}
			<span className="min-w-0 flex-1 truncate">{children}</span>
			{badge !== undefined && (
				<span
					className={`badge grid h-6 min-w-6 place-items-center rounded-md px-1.5 text-xs font-semibold tabular-nums ${
						attention ? "bg-orange-100 text-orange-700" : "bg-slate-100 text-slate-600"
					}`}
					aria-label={`${badge} open job${badge === 1 ? "" : "s"}${attention ? ", needs attention" : ""}`}
				>
					{badge}
				</span>
			)}
		</NavLink>
	);
}
