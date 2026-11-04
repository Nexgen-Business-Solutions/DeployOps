// The suite layout's landing screen: my open work across the five checklists at a glance.

import { ArrowRight, BriefcaseBusiness, CircleCheck, TriangleAlert } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Link } from "react-router";

import { Banner, Skeleton } from "../components/ui";
import { CardIcon } from "../components/CardIcon";
import { CARD_COLORS, DEFAULT_COLOR, plural, summarize } from "../lib/cards";
import { useSession } from "../lib/session";
import { useShell } from "../lib/shell";
import type { Card } from "../lib/types";

function greeting(now: Date): string {
	const hour = now.getHours();
	return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
}

export default function Overview() {
	const me = useSession();
	const { cards, error, loading } = useShell();
	const [now] = useState(() => new Date());
	const summary = cards ? summarize(cards) : null;

	return (
		<main className="mx-auto max-w-[96rem] px-4 pb-16 pt-6 sm:px-6 lg:px-8">
			<h2 className="text-xl font-semibold tracking-tight text-slate-900 sm:text-2xl">Overview</h2>
			<p className="mt-1 text-sm text-slate-500">
				{greeting(now)}, {me.full_name.split(" ")[0]} · {now.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })}
			</p>

			{error && (
				<div className="mt-6">
					<Banner>{error.message}</Banner>
				</div>
			)}

			<section className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6" aria-label="Open jobs">
				{loading && !cards ? (
					Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-[7.5rem] bg-white" />)
				) : (
					<>
						<Stat
							icon={
								<span className="grid size-10 place-items-center rounded-xl bg-blue-50 text-blue-600 ring-1 ring-blue-100">
									<BriefcaseBusiness className="size-5" strokeWidth={1.75} />
								</span>
							}
							label="My open jobs"
							value={summary?.open ?? 0}
							note={summary?.attention ? `${plural(summary.attention, "job")} need attention` : "All up to date"}
							warn={Boolean(summary?.attention)}
						/>
						{cards?.map((card) => <CardStat key={card.id} card={card} />)}
					</>
				)}
			</section>

			<div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
				<Panel title="Open jobs by checklist">
					{loading && !cards ? (
						<Skeleton className="h-48" />
					) : summary && summary.busiest.length ? (
						<OpenJobBars cards={summary.busiest} />
					) : (
						<Quiet icon={<CircleCheck className="size-5" />} title="No open jobs" text="Jobs assigned to you appear here." />
					)}
				</Panel>

				<Panel title="Needs attention">
					{loading && !cards ? (
						<Skeleton className="h-48" />
					) : summary && summary.needsAttention.length ? (
						<ul className="divide-y divide-slate-100">
							{summary.needsAttention.map((card) => (
								<li key={card.id}>
									<Link to={`/c/${card.id}`} className="group -mx-2 flex items-start gap-4 rounded-xl px-2 py-3 hover:bg-slate-50">
										<span className="grid size-10 shrink-0 place-items-center rounded-full bg-orange-50 text-orange-600 ring-1 ring-orange-100">
											<TriangleAlert className="size-[18px]" strokeWidth={1.75} />
										</span>
										<span className="min-w-0 flex-1">
											<span className="block font-semibold text-slate-900">
												{plural(card.attention, "job")} in {card.title}
											</span>
											<span className="block text-sm text-slate-500">Draft or returned for correction</span>
										</span>
										<ArrowRight className="mt-2 size-4 shrink-0 text-slate-300 group-hover:text-blue-600" aria-hidden />
									</Link>
								</li>
							))}
						</ul>
					) : (
						<Quiet icon={<CircleCheck className="size-5" />} title="Nothing needs attention" text="No drafts or jobs returned for correction." />
					)}
				</Panel>
			</div>
		</main>
	);
}

function Stat({ icon, label, value, note, warn }: { icon: ReactNode; label: string; value: number; note: string; warn?: boolean }) {
	return (
		<div className="flex h-full flex-col rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200/70">
			<div className="flex items-start gap-3">
				{icon}
				<div className="min-w-0">
					<p className="truncate text-[13px] text-slate-600">{label}</p>
					<p className="text-2xl font-bold tabular-nums leading-tight text-slate-900">{value}</p>
				</div>
			</div>
			<p className={`mt-3 truncate text-[13px] ${warn ? "text-orange-600" : "text-slate-400"}`}>{note}</p>
		</div>
	);
}

function CardStat({ card }: { card: Card }) {
	return (
		<Link to={`/c/${card.id}`} className="block rounded-2xl transition hover:-translate-y-0.5 hover:shadow-md">
			<Stat
				icon={
					<span className={`grid size-10 shrink-0 place-items-center rounded-xl ring-1 ${CARD_COLORS[card.id] ?? DEFAULT_COLOR}`}>
						<CardIcon card={card} className="size-5" strokeWidth={1.75} />
					</span>
				}
				label={card.title}
				value={card.open_jobs}
				note={card.attention ? `${card.attention} need${card.attention === 1 ? "s" : ""} attention` : card.subtitle}
				warn={card.attention > 0}
			/>
		</Link>
	);
}

function OpenJobBars({ cards }: { cards: Card[] }) {
	const most = Math.max(...cards.map((card) => card.open_jobs));
	return (
		<ul className="space-y-3">
			{cards.map((card) => (
				<li key={card.id}>
					<Link to={`/c/${card.id}`} className="group grid grid-cols-[minmax(0,9rem)_1fr_2.5rem] items-center gap-3 sm:grid-cols-[minmax(0,12rem)_1fr_3rem]">
						<span className="truncate text-sm text-slate-600 group-hover:text-slate-900">{card.title}</span>
						<span className="h-5 rounded-md bg-slate-100">
							<span className="block h-full rounded-md bg-blue-500 transition-[width] duration-500" style={{ width: `${(card.open_jobs / most) * 100}%` }} />
						</span>
						<span className="text-right text-sm font-medium tabular-nums text-slate-700">{card.open_jobs}</span>
					</Link>
				</li>
			))}
		</ul>
	);
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
	return (
		<section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200/70 sm:p-6">
			<h3 className="mb-5 text-base font-semibold text-slate-900">{title}</h3>
			{children}
		</section>
	);
}

function Quiet({ icon, title, text }: { icon: ReactNode; title: string; text: string }) {
	return (
		<div className="flex items-center gap-4 py-6">
			<span className="grid size-10 place-items-center rounded-full bg-emerald-50 text-emerald-600 ring-1 ring-emerald-100">{icon}</span>
			<span>
				<span className="block font-semibold text-slate-900">{title}</span>
				<span className="block text-sm text-slate-500">{text}</span>
			</span>
		</div>
	);
}
