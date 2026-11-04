// What the home grid, the suite sidebar and the overview share about the five checklists.

import { Bot, ClipboardCheck, Map, Settings, Wrench } from "lucide-react";
import type { ComponentType } from "react";

import type { Card } from "./types";

export type Icon = ComponentType<{ className?: string; strokeWidth?: number }>;

const ICONS: Record<string, Icon> = {
	"clipboard-check": ClipboardCheck,
	wrench: Wrench,
	map: Map,
	bot: Bot,
	settings: Settings,
};

export function cardIcon(card: Card): Icon {
	return ICONS[card.icon] ?? ClipboardCheck;
}

/** Soft tile colours per checklist (icon, background, ring), the same in every layout. */
export const CARD_COLORS: Record<string, string> = {
	"cashmatic-preinstall": "bg-blue-100/80 text-blue-600 ring-blue-200/60",
	"cashmatic-onsite": "bg-emerald-100/80 text-emerald-600 ring-emerald-200/60",
	"bellabot-preinstall": "bg-violet-100/80 text-violet-600 ring-violet-200/60",
	"bellabot-onsite": "bg-amber-100/80 text-amber-600 ring-amber-200/60",
	"cashmatic-maintenance": "bg-teal-100/80 text-teal-600 ring-teal-200/60",
};

export const DEFAULT_COLOR = "bg-zinc-100 text-ink ring-zinc-200";

export type Summary = {
	open: number;
	attention: number;
	/** Checklists that have open jobs, most first; ties keep the cards' order. */
	busiest: Card[];
	/** Checklists with jobs needing attention (draft or returned for correction), most first. */
	needsAttention: Card[];
};

export function summarize(cards: Card[]): Summary {
	const byCount = (key: "open_jobs" | "attention") =>
		cards.filter((card) => card[key] > 0).sort((a, b) => b[key] - a[key]);
	return {
		open: cards.reduce((sum, card) => sum + card.open_jobs, 0),
		attention: cards.reduce((sum, card) => sum + card.attention, 0),
		busiest: byCount("open_jobs"),
		needsAttention: byCount("attention"),
	};
}

export function plural(count: number, word: string): string {
	return `${count} ${word}${count === 1 ? "" : "s"}`;
}
