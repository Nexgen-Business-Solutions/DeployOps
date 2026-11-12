import { ReferenceCard } from "../components/form/ReferenceCard";
import { getPlugin, type RenderContext } from "./fields";
import { displayValue, isRequired, visibleSections } from "./logic";
import type { Answers, Definition, FieldDef, ScreenReference } from "./types";
export type FormRendererProps = {
	definition: Definition;
	answers: Answers;
	ctx: RenderContext;
	errors?: Map<string, string>;
	references?: ScreenReference[];
	onChange?: (fieldId: string, value: unknown) => void;
};
function groups(fields: FieldDef[]): FieldDef[][] {
	const out: FieldDef[][] = []; for (const f of fields) {
		const last = out.at(-1);
		if (f.type === "checkbox" && last?.[0].type === "checkbox")
			last.push(f);
		else
			out.push([f]);
	} return out;
}
export function FormRenderer({ definition, answers, ctx, errors = new Map(), references = [], onChange }: FormRendererProps) {
	function refs(id: string) { return references.filter(r => r.show_in.includes(id)).map(r => <ReferenceCard key={`${r.url}-${r.title}`} reference={{ ...r, section: null }} />); }
	return <>{visibleSections(definition, answers).map((section, index) => <section key={section.id} id={`s-${section.id}`} className="scroll-mt-28 mt-10 border-t border-line pt-8"><header className="mb-5"><p className="font-mono text-xs text-zinc-400">{String(index + 1).padStart(2, "0")}</p><h3 className="mt-1 text-xl font-semibold tracking-tight">{section.title}</h3>{section.description && <p className="mt-1 text-sm text-muted">{section.description}</p>}<div className="mt-3 space-y-2">{refs(section.id)}</div></header><div className="space-y-6">{groups(section.fields).map(group => <div key={group[0].id}>{group.map(field => { const plugin = getPlugin(field.type), Input = plugin.Input, error = errors.get(field.id), locked = !!field.fill_from?.locked, inputId = `input-${field.id}`; return <div id={`f-${field.id}`} key={field.id} className="scroll-mt-28"><label htmlFor={plugin.labelable ? inputId : undefined} className="mb-2 block text-[15px] font-medium">{field.label}{ctx.mode !== "readonly" && isRequired(field, answers) && <span className="ml-1 text-brand-500">*</span>}</label>{field.help && <p className="mb-2 text-sm text-muted">{field.help}</p>}<Input field={field} value={displayValue(field, answers, ctx.values, ctx.mode)} disabled={ctx.mode === "readonly" || locked} invalid={!!error} inputId={inputId} describedBy={error ? `error-${field.id}` : undefined} ctx={ctx} onChange={value => onChange?.(field.id, value)} />{locked && <p className="mt-1 text-sm text-muted">From the job</p>}<div className="mt-2 space-y-2">{refs(field.id)}</div>{error && <p id={`error-${field.id}`} role="alert" className="mt-2 text-sm text-red-600">{error}</p>}</div>; })}</div>)}</div></section>)}</>;
}
