// Share-form settings: types and pure helpers used by ShareSettings.
export type Audience = "Public" | "Roles" | "Users";
export type ShareValue = {audience: Audience; roles: string[]; users: {user: string; full_name: string}[]; entry_limit: "Multiple" | "Once"};
export type AudienceOption = {value: string; label?: string; email?: string};
export type Search = (kind: "role" | "user", txt: string) => Promise<AudienceOption[]>;

export const ONCE_PUBLIC_NOTE = "On public forms, “once” is per device. A private window or another device can get through, and identical machines may be treated as one.";

export function liveText(audience: Audience): string {
	return audience === "Public" ? "Anyone with this link can fill the form." : "People you chose can fill the form after signing in.";
}

export function sharePayload(form: string, v: ShareValue) {
	return {
		form, audience: v.audience, entry_limit: v.entry_limit,
		roles: v.audience === "Roles" ? v.roles : [],
		users: v.audience === "Users" ? v.users.map(u => u.user) : [],
	};
}

