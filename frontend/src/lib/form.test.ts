import { describe, expect, it } from "vitest";

import { plainText } from "./api";
import { conditionMet, findProblems, progress, toInputTime, visibleSections } from "./form";
import type { Field, Section } from "./types";

const field = (fieldname: string, fieldtype: string, extra: Partial<Field> = {}): Field => ({
	fieldname,
	fieldtype,
	label: fieldname,
	description: null,
	reqd: false,
	show: null,
	...extra,
});

const sections: Section[] = [
	{
		name: "steps",
		label: "Steps",
		description: null,
		any_of: false,
		fields: [field("step_a", "Check", { reqd: true }), field("note", "HTML", { text: "Read the guide" })],
	},
	{
		name: "pos",
		label: "POS",
		description: null,
		any_of: false,
		fields: [
			field("pos", "Select", { reqd: true, options: ["Yes", "No"] }),
			field("brand", "Data", { reqd: true, show: { field: "pos", value: "Yes" } }),
		],
	},
	{
		name: "training",
		label: "Training",
		description: null,
		any_of: true,
		fields: [field("t1", "Check"), field("t2", "Check")],
	},
	{
		name: "photos",
		label: "Photos",
		description: null,
		any_of: false,
		fields: [
			field("photos", "Table", {
				reqd: true,
				table: { kind: "photos", columns: [], file_column: "image", min_rows: 3 },
			}),
		],
	},
];

describe("conditions", () => {
	it("show a field only for the matching answer", () => {
		expect(conditionMet({ field: "pos", value: "Yes" }, { pos: "Yes" })).toBe(true);
		expect(conditionMet({ field: "pos", value: "Yes" }, { pos: "No" })).toBe(false);
		expect(visibleSections(sections, { pos: "No" })[1].fields.map((f) => f.fieldname)).toEqual(["pos"]);
	});
});

describe("findProblems", () => {
	it("lists required steps, answers, at-least-one groups and photo minimums", () => {
		const problems = findProblems(sections, { photos: [{ image: "/a" }] });
		expect([...problems.keys()]).toEqual(["step_a", "pos", "training", "photos"]);
		expect(problems.get("photos")).toBe("Add at least 3.");
	});

	it("requires a conditional field only when it is shown", () => {
		const base = { step_a: 1, t2: 1, photos: [{ image: "/a" }, { image: "/b" }, { image: "/c" }] };
		expect(findProblems(sections, { ...base, pos: "No" }).size).toBe(0);
		expect([...findProblems(sections, { ...base, pos: "Yes" }).keys()]).toEqual(["brand"]);
	});
});

describe("progress", () => {
	it("counts required answers given", () => {
		expect(progress(sections, {})).toBe(0);
		expect(progress(sections, { step_a: 1, pos: "No" })).toBe(0.5);
	});
});

describe("helpers", () => {
	it("formats times for inputs", () => {
		expect(toInputTime("9:05:00")).toBe("09:05");
	});

	it("turns ERPNext address HTML into clean lines", () => {
		expect(plainText("Rue Joss<br>\nBonanjo<br>\n\nDouala &amp; Co<br>")).toBe("Rue Joss\nBonanjo\nDouala & Co");
	});
});
