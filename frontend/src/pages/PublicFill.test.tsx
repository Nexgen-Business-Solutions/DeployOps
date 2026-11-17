import { expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { PublicFill, ThankYou, type PublicInfo } from "./PublicFill";

const info: PublicInfo = {
	name: "f1", title: "Customer survey", subtitle: "Two minutes", audience: "Public", entry_limit: "Once",
	login_required: false, can_start: true, reason: null, mine: [], references: [],
	definition: {schema: 1, sections: [{id: "s_aaaaaa", title: "About you", fields: [{id: "f_aaaaaa", key: "name", type: "text", label: "Your name", required: true}]}]},
};

it("renders the questions and a send button", () => {
	const html = renderToStaticMarkup(<PublicFill info={info} />);
	expect(html).toContain("Customer survey");
	expect(html).toContain("Your name");
	expect(html).toContain("Send");
});

it("shows the reason instead of the form when filling is refused", () => {
	const html = renderToStaticMarkup(<PublicFill info={{...info, can_start: false, reason: "You've already filled this form."}} />);
	expect(html).toContain("You&#x27;ve already filled this form.");
	expect(html).not.toContain("Your name");
});

it("thanks the visitor after sending", () => {
	expect(renderToStaticMarkup(<ThankYou title="Customer survey" />)).toContain("Thank you, your answers were sent.");
});
