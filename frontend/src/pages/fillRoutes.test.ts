import { expect, it } from "vitest";
import { entryPath, fillView, isFillPath, outsideFill } from "./fillRoutes";

it("routes share links outside the signed-in app", () => {
	expect(isFillPath("/deployops/f/abc")).toBe(true);
	expect(isFillPath("/deployops/f/abc/entry/SUB-1")).toBe(true);
	expect(isFillPath("/deployops/form/X/Y")).toBe(false);
	expect(isFillPath("/deployops/job/f")).toBe(false);
});

it("picks the screen for a visitor", () => {
	expect(fillView({login_required: true}, false)).toBe("login");
	expect(fillView({login_required: false}, false)).toBe("public");
	expect(fillView({login_required: false}, true)).toBe("entries");
});

it("builds the bare entry path", () => {
	expect(entryPath("a b", "SUB/1")).toBe("/f/a%20b/entry/SUB%2F1");
});

it("leaves the share-link router with a full page load for unknown paths", () => {
	expect(outsideFill()).toBe("/deployops/");
});
