import { describe, expect, it } from "vitest";
import { browserId, deviceHash, randomId, type IdEnv } from "./fingerprint";

function memoryEnv(overrides: Partial<IdEnv> = {}): IdEnv & {cookieValue: () => string} {
	const store = new Map<string, string>();
	let cookie = "";
	let n = 0;
	return {
		storage: {getItem: k => store.get(k) ?? null, setItem: (k, v) => void store.set(k, v)},
		readCookie: () => cookie,
		writeCookie: v => {cookie = v;},
		uuid: () => `id-${++n}`,
		cookieValue: () => cookie,
		...overrides,
	};
}

describe("browserId", () => {
	it("is stable across calls", () => {
		const env = memoryEnv();
		expect(browserId(env)).toBe(browserId(env));
	});
	it("falls back to the cookie when storage throws", () => {
		const env = memoryEnv({storage: {getItem: () => {throw new Error("blocked");}, setItem: () => {throw new Error("blocked");}}});
		const first = browserId(env);
		expect(env.cookieValue()).toContain(first);
		expect(browserId(env)).toBe(first);
	});
	it("reads an id kept only in the cookie", () => {
		const env = memoryEnv({storage: null});
		env.writeCookie("other=1; fc_bid=kept-id");
		expect(browserId(env)).toBe("kept-id");
	});
});

describe("deviceHash", () => {
	it("is 64 hex characters and the same for the same traits", async () => {
		const a = await deviceHash(["1920x1080", "Linux", "Africa/Douala"]);
		expect(a).toMatch(/^[0-9a-f]{64}$/);
		expect(await deviceHash(["1920x1080", "Linux", "Africa/Douala"])).toBe(a);
		expect(await deviceHash(["1280x720", "Linux", "Africa/Douala"])).not.toBe(a);
	});
});

describe("plain HTTP (no crypto.subtle, no randomUUID)", () => {
	it("still makes a stable 64-hex device hash", async () => {
		const a = await deviceHash(["1920x1080", "Linux"], null);
		expect(a).toMatch(/^[0-9a-f]{64}$/);
		expect(await deviceHash(["1920x1080", "Linux"], null)).toBe(a);
		expect(await deviceHash(["1280x720", "Linux"], null)).not.toBe(a);
	});
	it("still makes random ids", () => {
		const a = randomId({}), b = randomId({});
		expect(a).toMatch(/^[0-9a-f-]{20,}$/);
		expect(a).not.toBe(b);
	});
});
