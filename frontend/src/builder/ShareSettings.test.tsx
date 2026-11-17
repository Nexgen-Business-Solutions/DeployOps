import { expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { ShareSettingsView } from "./ShareSettings";
import { liveText, sharePayload, type ShareValue } from "./share";

const base: ShareValue = {audience: "Public", roles: ["DeployOps Technician"], users: [{user: "jane@x.com", full_name: "Jane"}], entry_limit: "Multiple"};
const view = (value: ShareValue, error = "") => renderToStaticMarkup(<ShareSettingsView form="f1" title="Survey" value={value} error={error} saving={false} onChange={() => {}} search={async () => []} />);

it("sends only the list the audience uses", () => {
	expect(sharePayload("f1", {...base, audience: "Users"})).toEqual({form: "f1", audience: "Users", roles: [], users: ["jane@x.com"], entry_limit: "Multiple"});
	expect(sharePayload("f1", {...base, audience: "Roles"})).toEqual({form: "f1", audience: "Roles", roles: ["DeployOps Technician"], users: [], entry_limit: "Multiple"});
	expect(sharePayload("f1", base)).toEqual({form: "f1", audience: "Public", roles: [], users: [], entry_limit: "Multiple"});
});

it("shows the user picker for Users and hides the roles", () => {
	const html = view({...base, audience: "Users"});
	expect(html).toContain("Jane");
	expect(html).not.toContain("DeployOps Technician");
});

it("explains the per-device limit only on public forms", () => {
	expect(view({...base, entry_limit: "Once"})).toContain("per device");
	expect(view({...base, audience: "Roles", entry_limit: "Once"})).not.toContain("per device");
});

it("shows a server error", () => {
	expect(view(base, "Choose at least one role who can fill this form.")).toContain("Choose at least one role");
});

it("describes who can open the link", () => {
	expect(liveText("Public")).toBe("Anyone with this link can fill the form.");
	expect(liveText("Users")).toBe("People you chose can fill the form after signing in.");
});

it("uses a compact segmented choice and a switch for one entry", () => {
	const html = view({...base, entry_limit: "Once"});
	expect(html).toContain('role="radiogroup"');
	expect(html).toMatch(/role="switch"[^>]*aria-checked="true"/);
	expect(view(base)).toMatch(/role="switch"[^>]*aria-checked="false"/);
});
