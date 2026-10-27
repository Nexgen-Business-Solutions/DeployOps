import { useState } from "react";

import { ApiError, post } from "../lib/api";
import type { Action } from "../lib/types";
import { ActionDialog, Button } from "./ui";

const DANGER = new Set(["block", "cancel", "return"]);

/** Workflow buttons exactly as the server allows them; each goes through a confirm / reason dialog. */
export function ActionButtons({
	actions,
	method,
	args,
	onDone,
	size = "md",
}: {
	actions: Action[];
	method: string;
	args: Record<string, unknown>;
	onDone: () => void;
	size?: "md" | "sm";
}) {
	const [current, setCurrent] = useState<Action | null>(null);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState<string | null>(null);

	async function run(reason: string) {
		if (!current) return;
		setBusy(true);
		setError(null);
		try {
			await post(method, { ...args, action: current.action, reason: reason || undefined });
			setCurrent(null);
			onDone();
		} catch (e) {
			setError(e instanceof ApiError ? e.message : String(e));
		} finally {
			setBusy(false);
		}
	}

	if (!actions.length) return null;
	// The first non-danger action is the main one; the rest are quiet.
	const main = actions.find((a) => !DANGER.has(a.action));
	return (
		<>
			<div className="flex flex-wrap gap-2">
				{actions.map((action) => (
					<Button
						key={action.action}
						variant={DANGER.has(action.action) ? "danger" : action === main ? "primary" : "secondary"}
						onClick={() => {
							setError(null);
							setCurrent(action);
						}}
						className={size === "sm" ? "h-9 px-4 text-sm" : ""}
					>
						{action.label}
					</Button>
				))}
			</div>
			<ActionDialog
				open={current !== null}
				title={current?.label ?? ""}
				needsReason={current?.reason_required ?? false}
				confirmLabel={current?.label ?? "Confirm"}
				busy={busy}
				error={error}
				onConfirm={(reason) => void run(reason)}
				onClose={() => setCurrent(null)}
			/>
		</>
	);
}
