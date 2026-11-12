import { expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { ConditionsEditor } from "./ConditionsEditor";
import { earlierFields, makePredicate } from "./conditions";
import { SettingsPanel } from "./SettingsPanel";
import type { Definition } from "../forms/types";
const definition: Definition = {schema: 1, sections: [{id: "s_aaaaaa", fields: [
	{id: "f_aaaaaa", key: "first", label: "Earlier", type: "yes_no"},
	{id: "f_bbbbbb", key: "second", label: "Current", type: "text"},
	{id: "f_cccccc", key: "third", label: "Later", type: "text"},
]}]};
it("offers only earlier fields and builds exact typed predicates", () => {
	const fields = earlierFields(definition, "f_bbbbbb"); expect(fields.map(f => f.label)).toEqual(["Earlier"]);
	const html = renderToStaticMarkup(<ConditionsEditor label="Show when" fields={fields} onChange={() => {}} />);
	expect(html).toContain("Show when");
	expect(makePredicate("f_aaaaaa", "eq", "No", "yes_no")).toEqual({field: "f_aaaaaa", op: "eq", value: "No"});
	expect(makePredicate("f_aaaaaa", "in", "A, B", "choice")).toEqual({field: "f_aaaaaa", op: "in", value: ["A", "B"]});
	expect(makePredicate("f_aaaaaa", "gte", "2", "number")).toEqual({field: "f_aaaaaa", op: "gte", value: 2});
	expect(makePredicate("f_aaaaaa", "empty", "", "text")).toEqual({field: "f_aaaaaa", op: "empty"});
});
it.each([
	["text", "Max length"], ["long_text", "No additional settings"], ["number", "Decimal"], ["currency", "Currency"],
	["choice", "Options"], ["multi_check", "Minimum selected"], ["checkbox", "Must be ticked"],
	["yes_no", "No additional settings"], ["date", "No additional settings"], ["time", "No additional settings"], ["datetime", "No additional settings"],
	["photos", "Captions"], ["files", "Extensions"], ["signature", "Signer from"], ["table", "Columns"], ["info", "Note text"],
])("renders %s config", (type, label) => {
	const field = {...definition.sections[0].fields[1], type};
	const html = renderToStaticMarkup(<SettingsPanel field={field} definition={definition} catalog={{field_types: [], values: [], outcomes: []}} onChange={() => {}} />);
	expect(html).toContain(label);
});
it("checkbox conditions offer a boolean value selector", () => {
	const html = renderToStaticMarkup(<ConditionsEditor label="Show" fields={[{id: "f_aaaaaa", key: "ack", label: "Ack", type: "checkbox"}]} value={{field: "f_aaaaaa", op: "eq", value: true}} onChange={() => {}} />);
	expect(html).toContain('value="true"'); expect(html).toContain('value="false"');
});
it.each([["text", "Max length"], ["number", "Decimal"], ["checkbox", "Must be ticked"], ["choice", "Display"]])("table %s columns expose nested config %s", (type, label) => {
	const field = {...definition.sections[0].fields[1], type: "table", config: {columns: [{id: "f_dddddd", type, label: "Column"}]}};
	const html = renderToStaticMarkup(<SettingsPanel field={field} definition={definition} catalog={{field_types: [], values: [], outcomes: []}} onChange={() => {}} />);
	expect(html).toContain(label);
});
it("numeric rule values can retain intermediate text until blur", () => {
	const html = renderToStaticMarkup(<ConditionsEditor label="Number" fields={[{id: "f_aaaaaa", key: "qty", label: "Quantity", type: "number"}]} value={{field: "f_aaaaaa", op: "gte", value: 2}} onChange={() => {}} />);
	expect(html).toContain('inputMode="decimal"');
});
it("lists each choice option in its own box with add and bulk edit", async () => {
	const { OptionsEditor } = await import("./OptionsEditor");
	const html = renderToStaticMarkup(<OptionsEditor options={["A long first option", "Second", "second"]} onChange={() => {}} />);
	expect(html.match(/aria-label="Option \d"/g)).toHaveLength(3);
	expect(html).toContain("Add option"); expect(html).toContain("Bulk edit"); expect(html).toContain("Duplicate option");
});
it("derives the key from the label until the designer types their own", async () => {
	const { isAutoKey, keyFor, slug } = await import("./SettingsPanel");
	expect(slug("Serial number (S/N)")).toBe("serial_number_s_n");
	expect(slug("Évaluation du site")).toBe("evaluation_du_site");
	expect(slug("2nd visit")).toBe("f_2nd_visit");
	expect(isAutoKey("field_abc123", "Short text")).toBe(true);
	expect(isAutoKey("serial_number", "Serial number")).toBe(true);
	expect(isAutoKey("serial_no", "Serial number")).toBe(false);
	expect(keyFor("Earlier", definition, "f_bbbbbb")).toBe("earlier");
	expect(keyFor("First", definition, "f_bbbbbb")).toBe("first_2");
});
it("offers a choice field's options as condition values", () => {
	const html = renderToStaticMarkup(<ConditionsEditor label="Show" fields={[{id: "f_aaaaaa", key: "kind", label: "Kind", type: "choice", config: {options: ["None", "Wall mounted"]}}]} value={{field: "f_aaaaaa", op: "ne", value: "None"}} onChange={() => {}} />);
	expect(html).toContain('<option value="Wall mounted">'); expect(html).toContain("Choose an answer");
});
