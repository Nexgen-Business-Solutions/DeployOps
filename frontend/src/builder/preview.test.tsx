import { expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { Preview } from "./Preview";
import { sampleValues } from "./sample";
it("renders preview at phone width using existing renderer and sample catalog keys", () => {
	const catalog = {field_types: [], outcomes: [], values: [{value: "serial_no", label: "Serial", type: "text"}]};
	expect(sampleValues(catalog)).toEqual({serial_no: "Sample Serial"});
	const html = renderToStaticMarkup(<Preview definition={{schema: 1, sections: [{id: "s_aaaaaa", title: "Preview section", fields: [{id: "f_aaaaaa", key: "sample", type: "text", label: "Sample"}]}]}} catalog={catalog} />);
	expect(html).toContain("375"); expect(html).toContain("Preview section"); expect(html).toContain("Fill sample job");
});
