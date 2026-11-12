import { expect, it } from "vitest";
import { FIELD_TYPES, getPlugin } from "./index";
import { textFromInput, numberFromInput, timeFromInput, timeToInput, datetimeFromInput } from "./convert";
const field = { id: "f_a", key: "a", label: "A", type: "number" };
it("registry has every server type except files ones", () => {
	for (const t of ["text", "long_text", "number", "currency", "checkbox", "yes_no", "date", "time", "datetime", "info", "choice", "multi_check", "table"])
		expect(FIELD_TYPES.map(p => p.type)).toContain(t);
});
it("conversions produce the server's shapes", () => { expect(textFromInput("")).toBeNull(); expect(numberFromInput("3", false)).toBe(3); expect(numberFromInput("-", true)).toBeNull(); expect(timeFromInput("08:30")).toBe("08:30:00"); expect(timeFromInput("")).toBeNull(); expect(timeToInput("08:30:00")).toBe("08:30"); expect(datetimeFromInput("2026-11-08T08:30")).toBe("2026-11-08 08:30:00"); });
it("isEmpty matches the server", () => { expect(getPlugin("text").isEmpty("")).toBe(true); expect(getPlugin("text").isEmpty(null)).toBe(true); expect(getPlugin("checkbox").isEmpty(false)).toBe(false); expect(getPlugin("multi_check").isEmpty({ selected: [], other: null })).toBe(true); expect(getPlugin("table").isEmpty([])).toBe(true); expect(getPlugin("choice").isEmpty({ other: "x" })).toBe(false); });
it("problems match the server messages", () => { expect(getPlugin("number").problems(0, { ...field, config: { min: 1 } })[0].message).toBe("Must be at least 1"); expect(getPlugin("table").problems([{ _row: "r_a", f_day: "Tue" }, { _row: "r_b", f_day: "Mon" }], { ...field, type: "table", config: { fixed_rows: { column: "f_day", labels: ["Mon", "Tue"] } } })[0].message).toBe("Rows must match the fixed row labels"); expect(getPlugin("table").problems([{}], { ...field, type: "table", config: { min_rows: 2 } })[0].message).toBe("Add at least 2 rows"); });
it("only allowed column types are inTable", () => expect(FIELD_TYPES.filter(p => p.inTable).map(p => p.type).sort()).toEqual(["text", "long_text", "number", "checkbox", "yes_no", "choice", "date", "time"].sort()));
it("getPlugin of an unknown type is the placeholder", () => expect(getPlugin("rating").hasValue).toBe(false));

import { choiceFromInput, otherOption } from "./convert";
it("switching to Other clears the previous option until text exists", () => { expect(choiceFromInput("Other", "Other", "")).toBeNull(); expect(choiceFromInput("Other", "Other", "Custom")).toEqual({ other: "Custom" }); });
it("literal Other is a normal option and synthetic Other never collides", () => { expect(choiceFromInput("Other", null, "")).toBe("Other"); expect(otherOption(["Other", "Other (specify)"])).toBe("Other (specify) (specify)"); });
