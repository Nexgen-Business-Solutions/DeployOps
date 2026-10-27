import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, post } from "./api";

function respond(status: number, body: unknown) {
	vi.stubGlobal("window", {});
	vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: status < 400, status, json: async () => body }));
}

afterEach(() => vi.unstubAllGlobals());

describe("post", () => {
	it("shows the reason Frappe gives in `message` when it refuses (update_password answers 410)", async () => {
		respond(410, { message: "Incorrect current password" });
		const error = await post("frappe.core.doctype.user.user.update_password", {}).catch((e: ApiError) => e);
		expect(error).toBeInstanceOf(ApiError);
		expect((error as ApiError).message).toBe("Incorrect current password");
		expect((error as ApiError).status).toBe(410);
	});

	it("prefers Frappe's server messages, e.g. a password policy refusal", async () => {
		respond(417, { _server_messages: JSON.stringify([JSON.stringify({ message: "Password is too weak" })]) });
		await expect(post("frappe.core.doctype.user.user.update_password", {})).rejects.toThrow("Password is too weak");
	});

	it("returns the message on success", async () => {
		respond(200, { message: "/app" });
		await expect(post("frappe.core.doctype.user.user.update_password", {})).resolves.toBe("/app");
	});
});
