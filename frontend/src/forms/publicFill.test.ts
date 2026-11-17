import { describe, expect, it } from "vitest";
import { clearDraft, loadDraft, saveDraft, sendPublic } from "./publicFill";

function memory() {
	const m = new Map<string, string>();
	return {getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v), removeItem: (k: string) => void m.delete(k)};
}
const broken = {getItem: () => {throw new Error("no");}, setItem: () => {throw new Error("no");}, removeItem: () => {throw new Error("no");}};

describe("public draft", () => {
	it("restores what was saved for that form only", () => {
		const s = memory();
		saveDraft("f1", {f_a: "Ann"}, s);
		expect(loadDraft("f1", s)).toEqual({f_a: "Ann"});
		expect(loadDraft("f2", s)).toEqual({});
		clearDraft("f1", s);
		expect(loadDraft("f1", s)).toEqual({});
	});
	it("works without storage", () => {
		expect(() => saveDraft("f1", {f_a: 1}, broken)).not.toThrow();
		expect(loadDraft("f1", broken)).toEqual({});
		expect(() => clearDraft("f1", broken)).not.toThrow();
		expect(loadDraft("f1", null)).toEqual({});
	});
	it("ignores a corrupt draft", () => {
		const s = memory();
		s.setItem("fc_draft:f1", "{not json");
		expect(loadDraft("f1", s)).toEqual({});
	});
});

describe("sendPublic", () => {
	it("posts the answers with the browser id and device hash", async () => {
		const calls: [string, Record<string, unknown>][] = [];
		const out = await sendPublic("f1", {f_a: "Ann"}, {
			post: async <T,>(method: string, args: Record<string, unknown>) => {calls.push([method, args]); return {name: "SUB-1"} as T;},
			browserId: () => "b-1",
			deviceHash: async () => "d-1",
		});
		expect(out).toEqual({name: "SUB-1"});
		expect(calls).toEqual([["forms_core.api.submit_public", {form: "f1", answers: {f_a: "Ann"}, browser_id: "b-1", device_hash: "d-1"}]]);
	});
});

describe("device ids failing", () => {
	it("still sends, with what could be read", async () => {
		const calls: Record<string, unknown>[] = [];
		await sendPublic("f1", {}, {
			post: async <T,>(_m: string, args: Record<string, unknown>) => {calls.push(args); return {name: "S"} as T;},
			browserId: () => "b-1",
			deviceHash: async () => {throw new Error("no crypto");},
		});
		expect(calls[0]).toMatchObject({browser_id: "b-1", device_hash: ""});
	});
});
