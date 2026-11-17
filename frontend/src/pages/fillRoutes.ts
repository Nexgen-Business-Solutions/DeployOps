// Share links (/deployops/f/...) run outside the signed-in app: guests, customers and staff without a
// DeployOps role open them too, so they never call DeployOps endpoints.
import { APP_BASE } from "../lib/paths";

export function isFillPath(pathname: string): boolean {
	return pathname === `${APP_BASE}/f` || pathname.startsWith(`${APP_BASE}/f/`);
}

/** login: restricted form, visitor not signed in. public: guest on a public form. entries: signed in. */
export function fillView(info: {login_required: boolean}, signedIn: boolean): "login" | "public" | "entries" {
	if (info.login_required) return "login";
	return signedIn ? "entries" : "public";
}

export const entryPath = (form: string, name: string) => `/f/${encodeURIComponent(form)}/entry/${encodeURIComponent(name)}`;

/** Unknown share-link paths leave this router with a full page load ("/" here would loop to "*"). */
export const outsideFill = () => `${APP_BASE}/`;
