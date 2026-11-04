import type { Reference, Section } from "./types";

/** Each document once, with the sections that use it. */
export function uniqueDocuments(references: Reference[], sections: Section[]): { reference: Reference; places: string[] }[] {
	const labels = new Map(sections.map((s) => [s.name, s.label]));
	const documents = new Map<string, { reference: Reference; places: string[] }>();
	for (const reference of references) {
		const entry = documents.get(reference.url) ?? { reference, places: [] };
		const label = reference.section ? labels.get(reference.section) : undefined;
		if (label && !entry.places.includes(label)) entry.places.push(label);
		documents.set(reference.url, entry);
	}
	return [...documents.values()];
}
