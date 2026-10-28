import { Check, Eye, EyeOff } from "lucide-react";
import { type FormEvent, useState } from "react";
import { Link } from "react-router";

import { Banner, Button, Page, TopBar } from "../components/ui";
import { post } from "../lib/api";

// Frappe's own endpoint: it checks the current password and the site's password policy.
const UPDATE_PASSWORD = "frappe.core.doctype.user.user.update_password";

function PasswordInput({
	label,
	value,
	onChange,
	autoComplete,
}: {
	label: string;
	value: string;
	onChange: (value: string) => void;
	autoComplete: "current-password" | "new-password";
}) {
	const [show, setShow] = useState(false);
	return (
		<label className="relative block">
			<span className="mb-1.5 block text-sm font-medium">{label}</span>
			<input
				className="field-input pr-12"
				type={show ? "text" : "password"}
				autoComplete={autoComplete}
				value={value}
				onChange={(e) => onChange(e.target.value)}
				required
			/>
			<button
				type="button"
				onClick={() => setShow(!show)}
				className="absolute bottom-1.5 right-2 grid size-9 place-items-center rounded-full text-zinc-400 hover:text-ink"
				aria-label={show ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}
			>
				{show ? <EyeOff className="size-[18px]" /> : <Eye className="size-[18px]" />}
			</button>
		</label>
	);
}

/** Change the signed-in user's password without leaving /deployops. */
export default function ChangePassword() {
	const [current, setCurrent] = useState("");
	const [next, setNext] = useState("");
	const [confirm, setConfirm] = useState("");
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [done, setDone] = useState(false);

	async function submit(event: FormEvent) {
		event.preventDefault();
		setError(null);
		if (next !== confirm) {
			setError("The new passwords don't match.");
			return;
		}
		setBusy(true);
		try {
			await post(UPDATE_PASSWORD, { old_password: current, new_password: next });
			setDone(true);
			setCurrent("");
			setNext("");
			setConfirm("");
		} catch (e) {
			setError((e as Error).message);
		} finally {
			setBusy(false);
		}
	}

	return (
		<>
			<TopBar title="Change password" back="/" />
			<Page>
				{done ? (
					<div className="mx-auto max-w-sm space-y-6 pt-6">
						<Banner kind="success">Your password has been changed.</Banner>
						<Link to="/" className="inline-flex h-12 w-full items-center justify-center rounded-full bg-brand-500 text-[15px] font-medium text-white hover:bg-brand-600">
							Back to home
						</Link>
					</div>
				) : (
					<form onSubmit={submit} className="mx-auto max-w-sm space-y-4 pt-6">
						<PasswordInput label="Current password" value={current} onChange={setCurrent} autoComplete="current-password" />
						<PasswordInput label="New password" value={next} onChange={setNext} autoComplete="new-password" />
						<PasswordInput label="Confirm new password" value={confirm} onChange={setConfirm} autoComplete="new-password" />
						{error && <Banner>{error}</Banner>}
						<Button type="submit" loading={busy} className="w-full" icon={!busy && <Check className="size-[18px]" aria-hidden />}>
							Change password
						</Button>
					</form>
				)}
			</Page>
		</>
	);
}
