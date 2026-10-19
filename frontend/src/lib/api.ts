// Thin wrapper around Frappe's REST API (same approach as Trixapos: plain fetch, no SDK).
// Every rule is enforced on the server; this only sends requests and turns errors into messages.

export class ApiError extends Error {
	status: number;

	constructor(message: string, status: number) {
		super(message);
		this.status = status;
	}
}

declare global {
	interface Window {
		csrf_token?: string;
	}
}

function csrfToken(): string {
	const token = window.csrf_token ?? "";
	// In the Vite dev server the Jinja placeholder is not rendered.
	return token.includes("{{") || token === "None" ? "" : token;
}

/** Plain text from a Frappe message (they may contain <br>, <strong>, …). */
export function plainText(html: string): string {
	return html
		.replace(/<br\s*\/?>/gi, "\n")
		.replace(/<[^>]+>/g, "")
		.replace(/&nbsp;/g, " ")
		.replace(/&amp;/g, "&")
		.replace(/&lt;/g, "<")
		.replace(/&gt;/g, ">")
		.split("\n")
		.map((line) => line.trim())
		.filter(Boolean)
		.join("\n");
}

type FrappeBody = {
	message?: unknown;
	exc_type?: string;
	exception?: string;
	_server_messages?: string;
};

function errorMessage(body: FrappeBody | null, status: number): string {
	if (body?._server_messages) {
		try {
			const messages = (JSON.parse(body._server_messages) as string[]).map((raw) => {
				const parsed = JSON.parse(raw) as { message?: string };
				return plainText(parsed.message ?? raw);
			});
			if (messages.length) return messages.join("\n");
		} catch {
			// fall through to the generic message
		}
	}
	if (body?.exception) return plainText(body.exception.split(":").slice(1).join(":") || body.exception);
	if (status === 403) return "You are not allowed to do that.";
	if (status === 404) return "Not found.";
	return "Something went wrong. Please try again.";
}

async function request<T>(url: string, init: RequestInit): Promise<T> {
	let response: Response;
	try {
		response = await fetch(url, { credentials: "include", ...init });
	} catch {
		throw new ApiError("You're offline — check your connection.", 0);
	}
	let body: FrappeBody | null = null;
	try {
		body = (await response.json()) as FrappeBody;
	} catch {
		body = null;
	}
	if (!response.ok) throw new ApiError(errorMessage(body, response.status), response.status);
	return body?.message as T;
}

function encode(args: Record<string, unknown>): string {
	const params = new URLSearchParams();
	for (const [key, value] of Object.entries(args)) {
		if (value === undefined || value === null) continue;
		params.set(key, typeof value === "object" ? JSON.stringify(value) : String(value));
	}
	return params.toString();
}

/** GET a whitelisted method (read-only calls). */
export function get<T>(method: string, args: Record<string, unknown> = {}): Promise<T> {
	const query = encode(args);
	return request<T>(`/api/method/${method}${query ? `?${query}` : ""}`, {
		headers: { Accept: "application/json" },
	});
}

/** POST a whitelisted method (anything that changes data). */
export function post<T>(method: string, args: Record<string, unknown> = {}): Promise<T> {
	return request<T>(`/api/method/${method}`, {
		method: "POST",
		headers: {
			Accept: "application/json",
			"Content-Type": "application/json",
			"X-Frappe-CSRF-Token": csrfToken(),
		},
		body: JSON.stringify(args),
	});
}

export async function login(usr: string, pwd: string): Promise<void> {
	await request("/api/method/login", {
		method: "POST",
		headers: { Accept: "application/json", "Content-Type": "application/json" },
		body: JSON.stringify({ usr, pwd }),
	});
}

export async function logout(): Promise<void> {
	await post("logout");
}

/** Upload a file as a private attachment of a document; returns its URL. */
export async function uploadPrivateFile(file: Blob, filename: string, doctype: string, docname: string): Promise<string> {
	const form = new FormData();
	form.append("file", file, filename);
	form.append("is_private", "1");
	form.append("doctype", doctype);
	form.append("docname", docname);
	form.append("folder", "Home/Attachments");
	const result = await request<{ file_url: string }>("/api/method/upload_file", {
		method: "POST",
		headers: { Accept: "application/json", "X-Frappe-CSRF-Token": csrfToken() },
		body: form,
	});
	return result.file_url;
}
