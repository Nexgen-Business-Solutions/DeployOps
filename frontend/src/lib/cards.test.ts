import { describe, expect, it } from "vitest";

import { plural, summarize } from "./cards";
import type { Card } from "./types";

function card(id: string, open_jobs: number, attention = 0): Card {
	return {
		id,
		title: id,
		subtitle: "",
		job_type: "Installation",
		product_line: "Cashmatic",
		doctype: "DeployOps Cashmatic Installation",
		icon: "wrench",
		open_jobs,
		attention,
		waiting: attention > 0,
	};
}

describe("summarize", () => {
	it("totals open jobs and jobs needing attention", () => {
		const summary = summarize([card("a", 2, 1), card("b", 0), card("c", 5, 2)]);
		expect([summary.open, summary.attention]).toEqual([7, 3]);
	});

	it("lists only checklists with open jobs, busiest first, ties in card order", () => {
		const summary = summarize([card("a", 1), card("b", 0), card("c", 3), card("d", 1)]);
		expect(summary.busiest.map((c) => c.id)).toEqual(["c", "a", "d"]);
	});

	it("lists only checklists with jobs needing attention, most first", () => {
		const summary = summarize([card("a", 3, 1), card("b", 4, 0), card("c", 2, 2)]);
		expect(summary.needsAttention.map((c) => c.id)).toEqual(["c", "a"]);
	});

	it("is empty when there is no work", () => {
		const summary = summarize([card("a", 0), card("b", 0)]);
		expect(summary).toEqual({ open: 0, attention: 0, busiest: [], needsAttention: [] });
	});
});

describe("plural", () => {
	it("adds an s except for one", () => {
		expect([plural(0, "job"), plural(1, "job"), plural(2, "job")]).toEqual(["0 jobs", "1 job", "2 jobs"]);
	});
});
