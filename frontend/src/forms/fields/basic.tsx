import { CheckRow, Segmented } from "../../components/form/controls";
import type { FieldInputProps } from "./index";
import { datetimeFromInput, datetimeToInput, numberFromInput, textFromInput, timeFromInput, timeToInput } from "./convert";
export function BasicInput({ field, value, disabled, invalid, inputId, describedBy, compact, onChange }: FieldInputProps) {
	const c = field.config ?? {};
	if (field.type === "info")
		return <p className="whitespace-pre-line text-sm text-muted">{String(c.text ?? "")}</p>;
	if (field.type === "checkbox")
		return <CheckRow label={field.label} checked={value === true} disabled={disabled} invalid={invalid} onChange={onChange} />;
	if (field.type === "yes_no")
		return <Segmented options={["Yes", "No"]} value={typeof value === "string" ? value : null} disabled={disabled} onChange={onChange} small={compact} />;
	const props = { id: inputId, "aria-label": field.label, "aria-describedby": describedBy, "aria-invalid": invalid, disabled, className: "field-input", placeholder: "Never type passwords, PINs, OTPs or pairing codes." };
	if (field.type === "long_text")
		return <textarea {...props} rows={compact ? 2 : 4} value={String(value ?? "")} onChange={e => onChange(textFromInput(e.target.value))} />;
	const numeric = field.type === "number" || field.type === "currency";
	const type = numeric ? "number" : ({ datetime: "datetime-local", date: "date", time: "time" }[field.type] ?? "text");
	const shown = field.type === "time" ? timeToInput(value) : field.type === "datetime" ? datetimeToInput(value) : String(value ?? "");
	return <input {...props} type={type} value={shown} maxLength={field.type === "text" ? Number(c.max_length ?? 140) : undefined} step={numeric ? (c.decimal === false ? 1 : "any") : undefined} min={numeric && typeof c.min === "number" ? c.min : undefined} max={numeric && typeof c.max === "number" ? c.max : undefined} onChange={e => onChange(numeric ? numberFromInput(e.target.value, c.decimal !== false) : field.type === "time" ? timeFromInput(e.target.value) : field.type === "datetime" ? datetimeFromInput(e.target.value) : textFromInput(e.target.value))} />;
}
