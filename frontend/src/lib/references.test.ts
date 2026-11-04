import { describe, expect, it } from "vitest";

import { uniqueDocuments } from "./references";
import type { Reference, Section } from "./types";

const sections = [
	{ name: "setup", label: "Setup" },
	{ name: "activation", label: "Activation" },
] as Section[];

const ref = (url: string, section: string | null, title = url): Reference => ({ title, url, section });

describe("uniqueDocuments", () => {
	it("lists each file once, with every section that uses it, in first-seen order", () => {
		const docs = uniqueDocuments([ref("a.pdf", "setup"), ref("b.pdf", null), ref("a.pdf", "activation")], sections);
		expect(docs.map((d) => [d.reference.url, d.places])).toEqual([
			["a.pdf", ["Setup", "Activation"]],
			["b.pdf", []],
		]);
	});

	it("names a section once and ignores sections the form no longer has", () => {
		const docs = uniqueDocuments([ref("a.pdf", "setup"), ref("a.pdf", "setup"), ref("a.pdf", "gone")], sections);
		expect(docs[0].places).toEqual(["Setup"]);
	});

	it("is empty without references", () => {
		expect(uniqueDocuments([], sections)).toEqual([]);
	});
});
