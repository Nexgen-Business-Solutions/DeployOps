import { get, post } from "../lib/api";
import { APP_BASE } from "../lib/paths";
import type { Definition } from "../forms/types";
export const read = <T,>(method: string, args: Record<string, unknown> = {}) => get<T>(`forms_core.api.${method}`, args);
export const write = <T,>(method: string, args: Record<string, unknown> = {}) => post<T>(`forms_core.api.${method}`, args);
/** Matches forms_core_designer_roles (deployops/hooks.py). `me` sends short role names ("Manager", "Admin"). */
const DESIGNER_ROLES = ["Manager", "Admin", "DeployOps Manager", "DeployOps Administrator"];
export const isDesigner = (roles: string[], user?: string) => user === "Administrator" || roles.some(r => DESIGNER_ROLES.includes(r));
export type Version = {name: string; version_no: number; published_on: string; published_by: string; change_note: string};
export type FormRecord = {name: string; title: string; status: string; current_version: string | null; modified: string; modified_by: string; context_doctype: string | null; draft_definition: string | Definition; versions: Version[]; subtitle?: string; icon?: string; color?: string};
export type ListedForm = {name: string; title: string; status: string; subtitle?: string | null; current_version: string | null; context_doctype: string | null; modified: string; version_no: number | null; published_on: string | null; entries: number};
export type Catalog = {field_types: {type: string; label: string; config_schema: Record<string, unknown>}[]; values: {value: string; label: string; type: string}[]; outcomes: {effect: string; label: string}[]};
export type EntryRow = {name: string; status: "Draft" | "Submitted" | "Cancelled"; started_by: string; submitted_by: string | null; submitted_on: string | null; created: string; modified: string; version_no: number | null; context: string | null};
export type EntryList = {total: number; counts: Record<string, number>; rows: EntryRow[]};
export type EntryFilter = {status?: string; from_date?: string; to_date?: string};

export const JOB_CONTEXT = "DeployOps Job";
/** Standalone forms (no context) are filled from one share link, any number of times. */
export const isShareable = (form: {context_doctype: string | null; current_version: string | null; status: string}) => !form.context_doctype && !!form.current_version && form.status !== "Archived";
export const shareUrl = (form: string) => `${window.location.origin}${APP_BASE}/f/${encodeURIComponent(form)}`;
export function entriesExportUrl(form: string, format: "xlsx" | "csv", filter: EntryFilter = {}): string {
	const params = new URLSearchParams({form, file_format: format});
	for (const [key, value] of Object.entries(filter)) if (value) params.set(key, value);
	return `/api/method/forms_core.api.export_entries?${params}`;
}
export function download(data: unknown, title: string) {
	const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type: "application/json"}));
	const a = document.createElement("a"); a.href = url; a.download = `${title}.json`; a.click(); URL.revokeObjectURL(url);
}
export function fileDownload(url: string) {
	const a = document.createElement("a"); a.href = url; a.rel = "noopener"; document.body.appendChild(a); a.click(); a.remove();
}
