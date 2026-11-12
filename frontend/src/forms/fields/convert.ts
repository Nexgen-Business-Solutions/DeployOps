export const textFromInput = (s: string): string | null => s === "" ? null : s;
export function numberFromInput(s: string, decimal: boolean): number | null {
	if (!s.trim() || !Number.isFinite(Number(s)))
		return null;
	return decimal ? Number(s) : Math.round(Number(s));
}
export const timeToInput = (v: unknown): string => typeof v === "string" ? v.slice(0, 5) : "";
export const timeFromInput = (s: string): string | null => s ? (s.length === 5 ? s + ":00" : s) : null;
export const datetimeToInput = (v: unknown): string => typeof v === "string" ? v.replace(" ", "T").slice(0, 16) : "";
export const datetimeFromInput = (s: string): string | null => s ? (s.length === 16 ? s + ":00" : s).replace("T", " ") : null;
export const dateFromInput = textFromInput;

/** The synthetic Other entry must not shadow a literal configured option. */
export function otherOption(options: string[]): string {
	let label = "Other";
	while (options.includes(label)) label += " (specify)";
	return label;
}
export function choiceFromInput(value: string | null, other: string | null, draft: string): unknown {
	return other !== null && value === other ? (draft.trim() ? { other: draft } : null) : value;
}
