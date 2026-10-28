import { Bot, ClipboardCheck, Map, Settings, SlidersHorizontal, Wrench } from "lucide-react";
import { type ComponentType, useState } from "react";
import { Link } from "react-router";

import { Banner, Page, Skeleton, TopBar } from "../components/ui";
import { UserMenu } from "../components/UserMenu";
import { useSession } from "../lib/session";
import type { Card } from "../lib/types";
import { useApi } from "../lib/useApi";

const ICONS: Record<string, ComponentType<{ className?: string; strokeWidth?: number }>> = {
    "clipboard-check": ClipboardCheck,
    wrench: Wrench,
    map: Map,
    bot: Bot,
    settings: Settings,
};

function greeting(now: Date): string {
    const hour = now.getHours();
    return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
}

export default function Home({ onLogout }: { onLogout: () => void }) {
    const me = useSession();
    const { data: cards, error, loading } = useApi<Card[]>("deployops.api.technician.home");
    const [now] = useState(() => new Date());
    const total = cards?.reduce((sum, card) => sum + card.open_jobs, 0) ?? 0;

    return (
        <>
            <TopBar right={<UserMenu onLogout={onLogout} />} />
            <Page>
                <p className="eyebrow">{now.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })}</p>
                <h2 className="mt-2 text-[32px] font-semibold leading-tight tracking-tight">
                    {greeting(now)}, {me.full_name.split(" ")[0]}
                </h2>
                <p className="mt-1 text-lg text-muted">
                    {loading && !cards ? "Loading your jobs…" : total ? `${total} open job${total === 1 ? "" : "s"}` : "No open jobs"}
                </p>

                {error && (
                    <div className="mt-6">
                        <Banner>{error.message}</Banner>
                    </div>
                )}

                <p className="eyebrow mt-12">Checklists</p>
                <ul className="mt-8 grid grid-cols-2 gap-x-6 gap-y-12 sm:grid-cols-3 sm:gap-x-10 sm:gap-y-14">
                    {loading && !cards
                        ? Array.from({ length: 6 }, (_, i) => (
                            <li key={i} className="flex flex-col items-center gap-3">
                                <Skeleton className="size-28 rounded-2xl md:size-32" />
                                <Skeleton className="h-3 w-20" />
                            </li>
                        ))
                        : cards && (
                            <>
                                {cards.map((card) => <CardTile key={card.id} card={card} />)}
                                <SettingsTile />
                            </>
                        )}
                </ul>
            </Page>
        </>
    );
}

const COLORS: Record<string, string> = {
    "cashmatic-preinstall": "bg-blue-100/80 text-blue-600 ring-blue-200/60",
    "cashmatic-onsite": "bg-emerald-100/80 text-emerald-600 ring-emerald-200/60",
    "bellabot-preinstall": "bg-violet-100/80 text-violet-600 ring-violet-200/60",
    "bellabot-onsite": "bg-amber-100/80 text-amber-600 ring-amber-200/60",
    "cashmatic-maintenance": "bg-teal-100/80 text-teal-600 ring-teal-200/60",
};

function CardTile({ card }: { card: Card }) {
    const Icon = ICONS[card.icon] ?? ClipboardCheck;
    return (
        <li>
            <Link to={`/c/${card.id}`} className="group flex flex-col items-center text-center">
                <span
                    className={`relative grid size-28 place-items-center rounded-2xl shadow-sm ring-1 transition group-hover:-translate-y-0.5 group-hover:shadow-md group-active:scale-95 md:size-32 ${COLORS[card.id] ?? "bg-zinc-100 text-ink ring-zinc-200"}`}
                >
                    <Icon className="size-10 md:size-12" strokeWidth={1.5} />
                    {card.open_jobs > 0 && (
                        <span
                            className={`absolute -right-2 -top-2 grid h-7 min-w-7 place-items-center rounded-full px-1.5 text-xs font-semibold bg-orange-500 text-white ring-2 ring-white`}
                            aria-label={`${card.open_jobs} open job${card.open_jobs === 1 ? "" : "s"}${card.waiting ? ", needs attention" : ""}`}
                        >
                            {card.open_jobs}
                        </span>
                    )}
                </span>
                <span className="mt-4 text-sm font-semibold leading-tight md:text-[15px] text-gray-500">{card.title}</span>
                <span className="mt-1 max-w-52 text-xs leading-snug text-muted md:text-[13px]">{card.subtitle}</span>
            </Link>
        </li>
    );
}

/** Placeholder for future settings and admin tools; not clickable yet. */
function SettingsTile() {
    return (
        <li>
            <div className="flex cursor-default flex-col items-center text-center" aria-disabled="true" title="Configurations for your account">
                <span className="relative grid size-28 place-items-center rounded-2xl bg-zinc-100 text-zinc-500 shadow-sm ring-1 ring-zinc-200 md:size-32">
                    <SlidersHorizontal className="size-10 md:size-12" strokeWidth={1.5} />
                </span>
                <span className="mt-4 text-sm font-semibold leading-tight text-gray-500 md:text-[15px]">Settings</span>
                <span className="mt-1 max-w-52 text-xs leading-snug text-muted md:text-[13px]">Configurations for your account</span>
            </div>
        </li>
    );
}
