import { createElement } from "react";

import { cardIcon } from "../lib/cards";
import type { Card } from "../lib/types";

/** A checklist's icon (the icons are fixed lucide components, looked up by the card's icon name). */
export function CardIcon({ card, className, strokeWidth }: { card: Card; className?: string; strokeWidth?: number }) {
	return createElement(cardIcon(card), { className, strokeWidth });
}
