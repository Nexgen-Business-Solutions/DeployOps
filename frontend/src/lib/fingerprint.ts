// "Fill only once" on public forms: a random browser ID plus a hash of device traits.
// Our own code, no service: raw traits never leave the browser, only their SHA-256.
// It deters repeat entries; a private window or another device gets through.

const KEY = "fc_bid";
const FONTS = ["Arial", "Calibri", "Cambria", "Comic Sans MS", "Consolas", "Courier New", "DejaVu Sans", "Georgia", "Helvetica Neue", "Liberation Sans", "Lucida Console", "Noto Sans", "Roboto", "Segoe UI", "SF Pro Text", "Tahoma", "Times New Roman", "Trebuchet MS", "Ubuntu", "Verdana"];

export type IdEnv = {
	storage: Pick<Storage, "getItem" | "setItem"> | null;
	readCookie: () => string;
	writeCookie: (value: string) => void;
	uuid: () => string;
};

function browserEnv(): IdEnv {
	let storage: IdEnv["storage"] = null;
	try { storage = window.localStorage; } catch { storage = null; }
	return {
		storage,
		readCookie: () => document.cookie,
		writeCookie: value => { document.cookie = value; },
		uuid: () => randomId(),
	};
}

/** crypto.randomUUID only exists on HTTPS or localhost; fall back so plain-HTTP pages still work. */
export function randomId(c: Partial<Crypto> | undefined = globalThis.crypto): string {
	if (c?.randomUUID) return c.randomUUID();
	const bytes = new Uint8Array(16);
	if (c?.getRandomValues) c.getRandomValues(bytes);
	else for (let i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256);
	const hex = Array.from(bytes, b => b.toString(16).padStart(2, "0")).join("");
	return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function fromCookie(cookie: string): string | null {
	const match = cookie.match(/(?:^|;\s*)fc_bid=([^;]+)/);
	return match ? decodeURIComponent(match[1]) : null;
}

/** This browser's random ID, kept in localStorage and a cookie; each storage may be blocked. */
export function browserId(env: IdEnv = browserEnv()): string {
	let id: string | null = null;
	try { id = env.storage?.getItem(KEY) ?? null; } catch { id = null; }
	id = id || fromCookie(env.readCookie()) || env.uuid();
	try { env.storage?.setItem(KEY, id); } catch { /* storage blocked: the cookie still holds it */ }
	try { env.writeCookie(`${KEY}=${encodeURIComponent(id)}; max-age=31536000; path=/; SameSite=Lax`); } catch { /* cookies blocked */ }
	return id;
}

function safe(read: () => unknown): string {
	try { const v = read(); return v === undefined || v === null ? "" : String(v); } catch { return ""; }
}

function webglRenderer(): string {
	const canvas = document.createElement("canvas");
	const gl = canvas.getContext("webgl") as WebGLRenderingContext | null;
	if (!gl) return "";
	const ext = gl.getExtension("WEBGL_debug_renderer_info");
	return String(gl.getParameter(ext ? ext.UNMASKED_RENDERER_WEBGL : gl.RENDERER) ?? "");
}

function canvasRender(): string {
	const canvas = document.createElement("canvas");
	canvas.width = 220; canvas.height = 30;
	const ctx = canvas.getContext("2d");
	if (!ctx) return "";
	ctx.textBaseline = "top"; ctx.font = "16px Arial"; ctx.fillStyle = "#f60"; ctx.fillRect(100, 1, 62, 20);
	ctx.fillStyle = "#069"; ctx.fillText("DeployOps forms ✓ 123", 2, 4);
	return canvas.toDataURL();
}

function installedFonts(): string {
	const ctx = document.createElement("canvas").getContext("2d");
	if (!ctx) return "";
	const sample = "mmmmmmmmmmlli10OO";
	ctx.font = "72px monospace";
	const base = ctx.measureText(sample).width;
	return FONTS.filter(font => { ctx.font = `72px "${font}", monospace`; return ctx.measureText(sample).width !== base; }).join(",");
}

/** Traits that stay the same across reloads of one browser on one device. Missing ones are "". */
export function deviceTraits(): string[] {
	const nav = navigator as Navigator & {deviceMemory?: number};
	return [
		safe(() => `${screen.width}x${screen.height}x${screen.colorDepth}`),
		safe(() => window.devicePixelRatio),
		safe(() => nav.platform),
		safe(() => Intl.DateTimeFormat().resolvedOptions().timeZone),
		safe(() => nav.language),
		safe(() => nav.hardwareConcurrency),
		safe(() => nav.deviceMemory),
		safe(webglRenderer),
		safe(canvasRender),
		safe(installedFonts),
	];
}

/** 64 hex characters from eight seeded FNV-1a passes, for pages without crypto.subtle (plain HTTP). */
function fallbackHash(text: string): string {
	let out = "";
	for (let seed = 0; seed < 8; seed++) {
		let h = (0x811c9dc5 ^ (seed * 0x9e3779b1)) >>> 0;
		for (let i = 0; i < text.length; i++) {h ^= text.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0;}
		out += h.toString(16).padStart(8, "0");
	}
	return out;
}

/** SHA-256 (hex) of the device traits; `subtle` null (plain HTTP) uses a non-cryptographic fallback. */
export async function deviceHash(traits: string[] = deviceTraits(), subtle: SubtleCrypto | null = globalThis.crypto?.subtle ?? null): Promise<string> {
	const text = traits.join("|");
	if (!subtle) return fallbackHash(text);
	const bytes = await subtle.digest("SHA-256", new TextEncoder().encode(text));
	return Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2, "0")).join("");
}
