// Small input controls shared by form fields and table cells.

import { Check } from "lucide-react";

/** A tappable row with a round tick, used for checklist steps. */
export function CheckRow({
	label,
	checked,
	disabled,
	invalid,
	onChange,
}: {
	label: string;
	checked: boolean;
	disabled: boolean;
	invalid?: boolean;
	onChange: (checked: boolean) => void;
}) {
	return (
		<button
			type="button"
			role="checkbox"
			aria-checked={checked}
			disabled={disabled}
			onClick={() => onChange(!checked)}
			className={`group flex w-full items-start gap-3.5 rounded-2xl px-3 py-3 text-left transition disabled:cursor-default ${
				disabled ? "" : "hover:bg-zinc-50 active:bg-zinc-100"
			}`}
		>
			<span
				className={`mt-px grid size-[22px] shrink-0 place-items-center rounded-full transition ${
					checked ? "bg-brand-500 text-white" : invalid ? "border-2 border-red-400" : "border-2 border-zinc-300 group-hover:border-zinc-400"
				}`}
			>
				{checked && <Check className="size-3.5" strokeWidth={3.2} />}
			</span>
			<span className={`text-[15px] leading-snug ${checked ? "text-ink" : "text-zinc-700"}`}>{label}</span>
		</button>
	);
}

/** Pills for two or three short options (Yes / No, Pass / Fail / Not Tested…). */
export function Segmented({
	options,
	value,
	disabled,
	onChange,
	small,
}: {
	options: string[];
	value: string | null;
	disabled: boolean;
	onChange: (value: string | null) => void;
	small?: boolean;
}) {
	return (
		<div className="grid gap-1 rounded-full bg-zinc-100 p-1" style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}>
			{options.map((option) => {
				const active = value === option;
				return (
					<button
						key={option}
						type="button"
						disabled={disabled}
						aria-pressed={active}
						onClick={() => onChange(active ? null : option)}
						className={`truncate rounded-full px-3 font-medium transition disabled:cursor-default ${small ? "h-8 text-[13px]" : "h-10 text-sm"} ${
							active ? (small ? "bg-white text-ink shadow-sm" : "bg-brand-500 text-white") : "text-muted hover:text-ink"
						}`}
					>
						{option}
					</button>
				);
			})}
		</div>
	);
}

/** A list of radio rows for longer option lists. */
export function RadioList({
	options,
	value,
	disabled,
	onChange,
}: {
	options: string[];
	value: string | null;
	disabled: boolean;
	onChange: (value: string) => void;
}) {
	return (
		<div role="radiogroup" className="-mx-3">
			{options.map((option) => {
				const active = value === option;
				return (
					<button
						key={option}
						type="button"
						role="radio"
						aria-checked={active}
						disabled={disabled}
						onClick={() => onChange(option)}
						className={`flex w-full items-center gap-3.5 rounded-2xl px-3 py-3 text-left transition disabled:cursor-default ${disabled ? "" : "hover:bg-zinc-50"}`}
					>
						<span className={`grid size-[22px] shrink-0 place-items-center rounded-full border-2 transition ${active ? "border-brand-500" : "border-zinc-300"}`}>
							{active && <span className="size-2.5 rounded-full bg-brand-500" />}
						</span>
						<span className="text-[15px]">{option}</span>
					</button>
				);
			})}
		</div>
	);
}
