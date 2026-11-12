export function newId(prefix: "s" | "f" | "r"): string {
	const chars = "abcdefghijklmnopqrstuvwxyz0123456789";
	return `${prefix}_${Array.from(crypto.getRandomValues(new Uint8Array(6)), n => chars[n % chars.length]).join("")}`;
}
