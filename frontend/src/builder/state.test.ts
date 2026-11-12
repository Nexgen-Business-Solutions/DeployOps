import { describe, it, expect } from "vitest";
import { History, reduce, dependencies, prepareAction } from "./state";
import { newId } from "./ids";
import type { Definition } from "../forms/types";
const def: Definition = {schema: 1, sections: [{id: "s_aaaaaa", fields: [
	{id: "f_aaaaaa", key: "table", label: "Table", type: "table", config: {columns: [{id: "f_bbbbbb", type: "text", label: "Column"}]}},
	{id: "f_cccccc", key: "dependent", type: "text", label: "Dependent", show: {field: "f_aaaaaa", op: "not_empty"}},
]}]};
describe("builder reducer", () => {
	it("generates server compatible IDs", () => expect(newId("f")).toMatch(/^f_[a-z0-9]{6}$/));
	it("duplicates with fresh field and column IDs and keys", () => {
		const next = reduce(def, prepareAction(def, {type: "duplicateField", id: "f_aaaaaa"}));
		expect(next.sections[0].fields).toHaveLength(3);
		expect(next.sections[0].fields[1].id).not.toBe("f_aaaaaa");
		expect(next.sections[0].fields[1].config?.columns).not.toEqual(def.sections[0].fields[0].config?.columns);
		expect(next.sections[0].fields[1].key).not.toBe("table");
		expect(def.sections[0].fields).toHaveLength(2);
	});
	it("reports references and removes conditions on delete", () => {
		expect(dependencies(def, ["f_aaaaaa"])).toContain("Dependent: Show when");
		const next = reduce(def, {type: "deleteField", id: "f_aaaaaa"});
		expect(next.sections[0].fields[0].show).toBeUndefined();
	});
	it("undo and redo round trip", () => {
		const h = new History(def); h.apply({type: "deleteField", id: "f_aaaaaa"}); const next = h.current;
		h.undo(); expect(h.current).toEqual(def); h.redo(); expect(h.current).toEqual(next);
		expect(h.canUndo).toBe(true); expect(h.canRedo).toBe(false);
	});
});
it("duplicates fixed tables with their row-label column remapped", () => {
	const source = structuredClone(def); source.sections[0].fields[0].config!.fixed_rows = {column: "f_bbbbbb", labels: ["Monday"]};
	const next = reduce(source, prepareAction(source, {type: "duplicateField", id: "f_aaaaaa"})); const copy = next.sections[0].fields[1];
	expect((copy.config!.fixed_rows as {column: string}).column).toBe((copy.config!.columns as {id: string}[])[0].id);
});
it("duplicates imported table column keys without collisions", () => {
	const source = structuredClone(def); (source.sections[0].fields[0].config!.columns as Record<string, unknown>[])[0].key = "column_key";
	const next = reduce(source, prepareAction(source, {type: "duplicateField", id: "f_aaaaaa"}));
	expect((next.sections[0].fields[1].config!.columns as Record<string, unknown>[])[0].key).not.toBe("column_key");
});
it("reduces a prepared duplicate action deterministically", () => {
	const action = {type: "duplicateSection" as const, id: "s_aaaaaa", ids: {s_aaaaaa: "s_dddddd", f_aaaaaa: "f_dddddd", f_bbbbbb: "f_eeeeee", f_cccccc: "f_ffffff"}};
	expect(reduce(def, action)).toEqual(reduce(def, action));
});
