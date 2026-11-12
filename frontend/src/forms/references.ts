import type { Reference } from "../lib/types";
import type { Definition, ScreenReference } from "./types";
export function toDocuments(refs: ScreenReference[], def: Definition): {
	references: Reference[];
	sections: {
		name: string;
		label: string;
	}[];
} {
	const ids = new Set(def.sections.map(s => s.id));
	return { sections: def.sections.map(s => ({ name: s.id, label: s.title ?? "" })), references: refs.flatMap(r => { const sections = r.show_in.filter(id => ids.has(id)); return (sections.length ? sections : [null]).map(section => ({ title: r.title, url: r.url, section })); }) };
}
