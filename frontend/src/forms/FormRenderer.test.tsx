import { expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { FormRenderer } from "./FormRenderer";
import { FIELD_TYPES } from "./fields";
import { toDocuments } from "./references";
import { isPdf } from "../lib/pdf";
import type { Definition, RenderMode } from "./types";
const types = ["text", "long_text", "number", "currency", "checkbox", "yes_no", "date", "time", "datetime", "info", "choice", "multi_check", "table", "photos", "files", "signature"];
const def: Definition = { schema: 1, sections: [{ id: "s_all", title: "All fields", fields: types.map((type, i) => ({ id: `f_${i}`, key: `key${i}`, type, label: `Label ${type}`, config: type === "info" ? { text: "<b>x</b>" } : {} })) }] };
const draw = (definition = def, mode: RenderMode = "fill") => renderToStaticMarkup(<FormRenderer definition={definition} answers={{}} ctx={{ mode, values: { serial: "SN" } }} />);
it("registry has all 16 server types", () => expect(FIELD_TYPES.map(p => p.type).sort()).toEqual([...types].sort()));
it("renders every type in fill and readonly", () => {
	for (const mode of ["fill", "readonly"] as const) {
		const html = draw(def, mode);
		for (const type of types)
			expect(html).toContain(`Label ${type}`);
	}
});
it("readonly renders no enabled input", () => {
	const controls = draw(def, "readonly").match(/<(input|textarea|select)\b[^>]*>/g) ?? []; expect(controls.length).toBeGreaterThan(0); for (const c of controls)
		expect(c).toContain('disabled=""');
});
it("locked fill_from field is disabled and says From the job", () => { const html = draw({ schema: 1, sections: [{ id: "s_a", fields: [{ id: "f_a", key: "a", label: "Serial", type: "text", fill_from: { value: "serial", locked: true } }] }] }); expect(html).toContain("From the job"); expect(html).toContain('disabled=""'); });
it("hidden section is not rendered", () => expect(draw({ schema: 1, sections: [{ id: "s_hide", title: "Hidden", show: { field: "x", op: "eq", value: true }, fields: def.sections[0].fields }] })).not.toContain("Hidden"));
it("unknown type renders a placeholder", () => { const html = draw({ schema: 1, sections: [{ id: "s_a", fields: [{ id: "f_unk", key: "u", label: "Rating", type: "rating" }, def.sections[0].fields[0]] }] }); expect(html).toContain("This field type is not supported in the app yet."); expect(html).toContain("Label text"); });
it("info text is not HTML", () => { expect(draw()).toContain("&lt;b&gt;x&lt;/b&gt;"); expect(draw()).not.toContain("<b>x</b>"); });
it("preview shows context values for fill_from fields", () => expect(draw({ schema: 1, sections: [{ id: "s_a", fields: [{ id: "f_a", key: "a", type: "text", label: "Serial", fill_from: { value: "serial" } }] }] }, "preview")).toContain('value="SN"'));
it("toDocuments maps section, field-only and top references", () => { const result = toDocuments([{ title: "A", url: "a", show_in: ["s_all"] }, { title: "B", url: "b", show_in: ["f_0"] }, { title: "C", url: "c", show_in: [] }], def); expect(result.references.map(r => r.section)).toEqual(["s_all", null, null]); expect(result.sections).toEqual([{ name: "s_all", label: "All fields" }]); });
it("isPdf recognises reference_file URLs", () => expect(isPdf("/api/method/forms_core.api.reference_file?submission=S&file=%2Fprivate%2Ffiles%2Fa.pdf")).toBe(true));
