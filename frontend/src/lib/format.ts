// Display helpers shared by the screens.

export function formatDate(value: string | null): string {
	if (!value) return "Not planned";
	const date = new Date(`${value.slice(0, 10)}T00:00:00`);
	return date.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
}

export function firstLine(text: string | null): string {
	return (text ?? "").split(/\n|<br\s*\/?>/i)[0]?.replace(/<[^>]+>/g, "").trim() ?? "";
}

export function initials(name: string): string {
	return name
		.split(/\s+/)
		.filter(Boolean)
		.slice(0, 2)
		.map((part) => part[0]?.toUpperCase())
		.join("");
}
