// A visitor without a login fills a public form in the browser and sends it in one go.
import { post as apiPost } from "../lib/api";
import { browserId as realBrowserId, deviceHash as realDeviceHash } from "../lib/fingerprint";
import type { Answers } from "./types";

type DraftStorage = Pick<Storage, "getItem" | "setItem" | "removeItem"> | null;

const draftKey = (form: string) => `fc_draft:${form}`;

function defaultStorage(): DraftStorage {
	try { return window.localStorage; } catch { return null; }
}

/** The visitor's unsent answers for this form; {} when storage is blocked or the draft is corrupt. */
export function loadDraft(form: string, storage: DraftStorage = defaultStorage()): Answers {
	try {
		const raw = storage?.getItem(draftKey(form));
		const value: unknown = raw ? JSON.parse(raw) : {};
		return value && typeof value === "object" && !Array.isArray(value) ? value as Answers : {};
	} catch { return {}; }
}

export function saveDraft(form: string, answers: Answers, storage: DraftStorage = defaultStorage()): void {
	try { storage?.setItem(draftKey(form), JSON.stringify(answers)); } catch { /* storage blocked: answers stay on the page */ }
}

export function clearDraft(form: string, storage: DraftStorage = defaultStorage()): void {
	try { storage?.removeItem(draftKey(form)); } catch { /* nothing to clear */ }
}

export type DeviceIds = {browser_id: string; device_hash: string};

/** Each ID on its own: one failing (blocked storage, no crypto) still sends the other. */
export async function deviceIds(deps: {browserId?: () => string; deviceHash?: () => Promise<string>} = {}): Promise<DeviceIds> {
	let browser_id = "", device_hash = "";
	try { browser_id = (deps.browserId ?? realBrowserId)(); } catch { browser_id = ""; }
	try { device_hash = await (deps.deviceHash ?? (() => realDeviceHash()))(); } catch { device_hash = ""; }
	return {browser_id, device_hash};
}

type SendDeps = {
	post?: <T>(method: string, args: Record<string, unknown>) => Promise<T>;
	browserId?: () => string;
	deviceHash?: () => Promise<string>;
};

export async function sendPublic(form: string, answers: Answers, deps: SendDeps = {}): Promise<{name: string}> {
	const send = deps.post ?? apiPost;
	return send<{name: string}>("forms_core.api.submit_public", {form, answers, ...await deviceIds(deps)});
}
