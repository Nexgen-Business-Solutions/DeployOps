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

describe("an Other answer", () => {
	const group: Section[] = [
		{
			name: "safety",
			label: "Safety",
			description: null,
			any_of: true,
			fields: [field("t1", "Check"), field("other", "Data", { any_of_other: true })],
		},
	];

	it("counts as the group's tick once it has text", () => {
		expect(findProblems(group, { other: "Ramp check" }).size).toBe(0);
		expect(progress(group, { other: "Ramp check" })).toBe(1);
	});

	it("does not count when it is blank", () => {
		expect(findProblems(group, { other: "  " }).has("safety")).toBe(true);
		expect(progress(group, { other: "  " })).toBe(0);
	});
});

describe("an answer that makes another required", () => {
	const group: Section[] = [
		{
			name: "safety",
			label: "Safety",
			description: null,
			any_of: false,
			fields: [
				field("result", "Select", { reqd: true, options: ["PASS", "FAIL"] }),
				field("details", "Small Text", { required_when: [{ field: "result", value: "FAIL" }] }),
			],
		},
	];

	it("asks for it only with that answer", () => {
		expect(findProblems(group, { result: "PASS" }).size).toBe(0);
		expect([...findProblems(group, { result: "FAIL" }).keys()]).toEqual(["details"]);
		expect(findProblems(group, { result: "FAIL", details: "Bumper" }).size).toBe(0);
	});

	it("shows it as required and counts it for progress", () => {
		expect(visibleSections(group, { result: "FAIL" })[0].fields[1].reqd).toBe(true);
		expect(progress(group, { result: "FAIL" })).toBe(0.5);
	});
});

describe("a number with a range", () => {
	const group: Section[] = [
		{
			name: "site",
			label: "Site",
			description: null,
			any_of: false,
			fields: [field("slope", "Float", { range: { min: 0, max: 90 } })],
		},
	];

	it("is refused outside it, and accepted at its limits or when left empty", () => {
		expect(findProblems(group, { slope: 91 }).get("slope")).toBe("Must be between 0 and 90.");
		expect(findProblems(group, { slope: -1 }).has("slope")).toBe(true);
		for (const slope of [0, 90, null]) expect(findProblems(group, { slope }).size).toBe(0);
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
