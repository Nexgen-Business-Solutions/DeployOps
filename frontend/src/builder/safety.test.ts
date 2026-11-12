import { expect, it, vi } from "vitest";
import { duplicateForm, replaceReference, conditionDepthAllowed, beforeRestore, publishChecked } from "./safety";
it("duplicates export with a new key", async () => {
	const send = vi.fn().mockResolvedValue("new");
	await duplicateForm({form: {key: "original"}}, send);
	expect(send.mock.calls[0][0].key).not.toBe("original");
});
it("upload appends against current references rather than captured snapshot", () => {
	const current = [{file: "old", title: "Edited", show_in: ["s_aaaaaa"]}];
	expect(replaceReference(current, {file: "new", title: "New", show_in: []})).toEqual([...current, {file: "new", title: "New", show_in: []}]);
});
it("permits at most four engine levels", () => {expect(conditionDepthAllowed(2)).toBe(true); expect(conditionDepthAllowed(3)).toBe(false);});
it("flushes before restore and sends latest modified", async () => {
	const calls: string[] = [];
	await beforeRestore(async () => {calls.push("flush");}, () => "latest", async modified => {calls.push(`restore:${modified}`);}, async () => {calls.push("reload");});
	expect(calls).toEqual(["flush", "restore:latest", "reload"]);
});
it("publish requires a fresh saved check and its token", async () => {
	const calls: string[] = [];
	await publishChecked(async () => {calls.push("flush");}, async () => {calls.push("check"); return {errors: [], modified: "latest"};}, async token => {calls.push(`publish:${token}`);});
	expect(calls).toEqual(["flush", "check", "publish:latest"]);
});
it("navigation stays in editor when saving fails", async () => {
	const {saveBeforeNavigation} = await import("./safety"); const proceed = vi.fn(), stay = vi.fn();
	await saveBeforeNavigation(async () => {throw new Error("offline");}, proceed, stay);
	expect(proceed).not.toHaveBeenCalled(); expect(stay).toHaveBeenCalledWith("offline");
});
it("links table-column publish errors to the owning field settings", async () => {
	const {errorTarget} = await import("./safety");
	const def = {schema: 1, sections: [{id: "s_aaaaaa", fields: [{id: "f_aaaaaa", key: "table", type: "table", label: "Table", config: {columns: [{id: "f_bbbbbb", type: "text", label: "Column"}]}}]}]};
	expect(errorTarget(def, "f_bbbbbb")).toBe("f_aaaaaa");
	expect(errorTarget(def, "s_aaaaaa")).toBe("s_aaaaaa");
});
it("treats the short Manager and Admin role names from `me` as designers", async () => {
	const { isDesigner } = await import("./api");
	expect(isDesigner(["Manager"], "manager@x")).toBe(true);
	expect(isDesigner(["Admin"], "admin@x")).toBe(true);
	expect(isDesigner(["Supervisor"], "sup@x")).toBe(false);
	expect(isDesigner(["Technician"], "tech@x")).toBe(false);
});
