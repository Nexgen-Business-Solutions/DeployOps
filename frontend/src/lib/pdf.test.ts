import { describe, expect, it } from "vitest";

import { isPdf } from "./pdf";

describe("isPdf", () => {
	it("recognises PDF files whatever the case or query string", () => {
		expect(isPdf("/private/files/cdig.pdf")).toBe(true);
		expect(isPdf("/private/files/CDIG.PDF?fid=1")).toBe(true);
		expect(isPdf("/private/files/logo.png")).toBe(false);
	});
});
