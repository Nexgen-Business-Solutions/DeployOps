import type { Catalog } from "./api";
export function sampleValues(catalog: Catalog): Record<string, unknown> {
	return Object.fromEntries(catalog.values.map(v => [v.value, v.type === "date" ? "2026-11-09" : v.type === "number" ? 1 : `Sample ${v.label}`]));
}
