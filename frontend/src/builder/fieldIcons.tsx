import { AlignLeft, Calendar, CalendarClock, Camera, CircleDot, Clock, Coins, Hash, Info, ListChecks, Paperclip, PenLine, SquareCheck, Table2, ToggleLeft, Type, type LucideIcon } from "lucide-react";

export const FIELD_ICONS: Record<string, LucideIcon> = {
	text: Type, long_text: AlignLeft, number: Hash, currency: Coins, choice: CircleDot, multi_check: ListChecks,
	checkbox: SquareCheck, yes_no: ToggleLeft, date: Calendar, time: Clock, datetime: CalendarClock,
	photos: Camera, files: Paperclip, signature: PenLine, table: Table2, info: Info,
};

export const FIELD_LABELS: Record<string, string> = {
	text: "Short text", long_text: "Long text", number: "Number", currency: "Amount", choice: "Single choice",
	multi_check: "Multiple choice", checkbox: "Checkbox", yes_no: "Yes / No", date: "Date", time: "Time",
	datetime: "Date & time", photos: "Photos", files: "Files", signature: "Signature", table: "Table", info: "Note",
};

/** Palette groups, in display order. Types the server offers but no group lists go under "Other". */
export const FIELD_GROUPS: [string, string[]][] = [
	["Basic", ["text", "long_text", "number", "currency"]],
	["Choices", ["choice", "multi_check", "yes_no", "checkbox"]],
	["Date & time", ["date", "time", "datetime"]],
	["Evidence", ["photos", "files", "signature"]],
	["Layout", ["table", "info"]],
];

export function FieldIcon({type, className = "size-4"}: {type: string; className?: string}) {
	const Icon = FIELD_ICONS[type] ?? Type;
	return <Icon className={className} aria-hidden strokeWidth={1.75} />;
}

export const fieldLabel = (type: string, fallback?: string) => FIELD_LABELS[type] ?? fallback ?? type;
