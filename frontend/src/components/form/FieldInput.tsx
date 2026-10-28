import { Info } from "lucide-react";

import { fromInputDatetime, toInputDatetime, toInputTime } from "../../lib/form";
import type { Field, Row, Value } from "../../lib/types";
import { CheckRow, RadioList, Segmented } from "./controls";
import { FilesField } from "./FilesField";
import { SignaturePad } from "./SignaturePad";
import { TableField } from "./TableField";

const NO_SECRETS = "Never type passwords, PINs, OTPs or pairing codes.";
const SECRET_PRONE = /ip|user|account|code|remarks|notes/i;

type Props = {
	field: Field;
	value: Value | undefined;
	error?: string;
	disabled: boolean;
	doctype: string;
	docname: string;
	signedBy?: { signer_name: string | null; signed_on: string | null };
	onChange: (value: Value) => void;
};

/** One field of a checklist form, chosen by its Frappe field type. */
export function FieldInput({ field, value, error, disabled: locked, doctype, docname, signedBy, onChange }: Props) {
	const disabled = locked || Boolean(field.read_only);
	if (field.fieldtype === "HTML") {
		return (
			<p className="flex gap-2.5 rounded-2xl bg-zinc-50 px-4 py-3 text-sm text-muted">
				<Info className="mt-0.5 size-4 shrink-0" aria-hidden /> {field.text}
			</p>
		);
	}

	if (field.fieldtype === "Check") {
		return (
			<div id={`f-${field.fieldname}`} className="-mx-3 scroll-mt-28">
				<CheckRow label={field.label} checked={Boolean(value)} disabled={disabled} invalid={Boolean(error)} onChange={(checked) => onChange(checked ? 1 : 0)} />
				{field.description && <p className="-mt-1 mb-1 pl-[3.1rem] text-[13px] text-muted">{field.description}</p>}
			</div>
		);
	}

	const text = typeof value === "string" ? value : value === null || value === undefined ? "" : String(value);
	const inputClass = `field-input ${error ? "field-input-error" : ""}`;
	// The heading names the control: a native input through <label for>, a composite one as a group.
	const ids = { input: `in-${field.fieldname}`, label: `l-${field.fieldname}`, description: `d-${field.fieldname}`, error: `e-${field.fieldname}` };
	const describedBy = [field.description && ids.description, error && ids.error].filter(Boolean).join(" ") || undefined;
	const native = { id: ids.input, "aria-required": field.reqd ? true : undefined, "aria-invalid": error ? true : undefined, "aria-describedby": describedBy };
	let labelable = true;
	let control;
	switch (field.fieldtype) {
		case "Select": {
			const options = field.options ?? [];
			const short = options.length <= 3 && options.every((o) => o.length <= 18);
			labelable = !short && options.length > 8;
			control = short ? (
				<Segmented options={options} value={text || null} disabled={disabled} onChange={onChange} />
			) : options.length <= 8 ? (
				<RadioList options={options} value={text || null} disabled={disabled} onChange={onChange} />
			) : (
				<select {...native} className={inputClass} value={text} disabled={disabled} onChange={(e) => onChange(e.target.value || null)}>
					<option value="">Select…</option>
					{options.map((option) => (
						<option key={option}>{option}</option>
					))}
				</select>
			);
			break;
		}
		case "Small Text":
		case "Text":
		case "Long Text":
			control = (
				<textarea
					{...native}
					className={`${inputClass} min-h-24 resize-y`}
					value={text}
					disabled={disabled}
					placeholder={disabled ? "" : NO_SECRETS}
					onChange={(e) => onChange(e.target.value)}
				/>
			);
			break;
		case "Int":
		case "Float":
		case "Currency":
			control = (
				<input
					{...native}
					className={inputClass}
					type="number"
					inputMode={field.fieldtype === "Int" ? "numeric" : "decimal"}
					step={field.fieldtype === "Int" ? 1 : "any"}
					value={text}
					disabled={disabled}
					onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
				/>
			);
			break;
		case "Date":
			control = <input {...native} className={inputClass} type="date" value={text.slice(0, 10)} disabled={disabled} onChange={(e) => onChange(e.target.value || null)} />;
			break;
		case "Datetime":
			control = (
				<input
					{...native}
					className={inputClass}
					type="datetime-local"
					value={toInputDatetime(value)}
					disabled={disabled}
					onChange={(e) => onChange(fromInputDatetime(e.target.value))}
				/>
			);
			break;
		case "Time":
			control = <input {...native} className={inputClass} type="time" value={toInputTime(value)} disabled={disabled} onChange={(e) => onChange(e.target.value ? `${e.target.value}:00` : null)} />;
			break;
		case "Signature":
			labelable = false;
			control = (
				<>
					<SignaturePad value={text || null} disabled={disabled} onChange={onChange} />
					{text && signedBy && (
						<p className="mt-2 text-[13px] text-muted">
							Signed by {signedBy.signer_name || "—"}
							{signedBy.signed_on ? ` · ${new Date(signedBy.signed_on.replace(" ", "T")).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}` : ""}
						</p>
					)}
				</>
			);
			break;
		case "Table": {
			const rows = (value as Row[] | undefined) ?? [];
			const table = field.table;
			if (!table) return null;
			labelable = false;
			control =
				table.kind === "photos" || table.kind === "files" ? (
					<FilesField table={table} rows={rows} disabled={disabled} doctype={doctype} docname={docname} onChange={onChange} />
				) : (
					<TableField table={table} rows={rows} disabled={disabled} onChange={onChange} />
				);
			break;
		}
		default:
			control = (
				<input
					{...native}
					className={inputClass}
					type={field.options?.[0] === "Email" ? "email" : "text"}
					value={text}
					disabled={disabled}
					placeholder={!disabled && SECRET_PRONE.test(field.fieldname) ? NO_SECRETS : undefined}
					onChange={(e) => onChange(e.target.value)}
				/>
			);
	}

	return (
		<div id={`f-${field.fieldname}`} className="scroll-mt-28">
			<div className="mb-2">
				<label id={ids.label} htmlFor={labelable ? ids.input : undefined} className="block text-[15px] font-medium">
					{field.label}
					{field.reqd && !disabled && (
						<span className="ml-0.5 text-brand-500" aria-hidden>
							*
						</span>
					)}
				</label>
				{field.description && (
					<p id={ids.description} className="mt-0.5 text-[13px] text-muted">
						{field.description}
					</p>
				)}
			</div>
			{labelable ? (
				control
			) : (
				<div role="group" aria-labelledby={ids.label} aria-describedby={describedBy}>
					{control}
				</div>
			)}
			{error && (
				<p id={ids.error} className="mt-1.5 text-[13px] text-red-600">
					{error}
				</p>
			)}
		</div>
	);
}
