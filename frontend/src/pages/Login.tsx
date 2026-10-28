import { ArrowRight, Eye, EyeOff } from "lucide-react";
import { type FormEvent, useState } from "react";

import { Banner, Button, Logo } from "../components/ui";
import { ApiError, login, logout } from "../lib/api";

/** `signedInAs`: a session exists but the account has no DeployOps role. */
export default function Login({ signedInAs }: { signedInAs?: string }) {
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [show, setShow] = useState(false);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState<string | null>(null);

	async function submit(event: FormEvent) {
		event.preventDefault();
		setBusy(true);
		setError(null);
		try {
			await login(email.trim(), password);
			// Reload so the page carries the new session's CSRF token.
			window.location.reload();
		} catch (e) {
			setBusy(false);
			setError(e instanceof ApiError && e.status === 401 ? "Wrong email or password." : (e as Error).message);
		}
	}

	return (
		<main className="grid min-h-svh place-items-center px-6 py-12">
			<form onSubmit={submit} className="w-full max-w-sm">
				<Logo size={44} />
				<h1 className="mt-8 text-[32px] font-semibold leading-tight tracking-tight">Sign in</h1>
				<p className="mt-2 text-muted">Field checklists for DeployOps technicians.</p>

				<div className="mt-10 space-y-3">
					<label className="block">
						<span className="sr-only">Email or username</span>
						<input
							className="field-input"
							type="text"
							autoComplete="username"
							autoCapitalize="none"
							autoCorrect="off"
							spellCheck={false}
							placeholder="Email or username"
							value={email}
							onChange={(e) => setEmail(e.target.value)}
							required
						/>
					</label>
					<label className="relative block">
						<span className="sr-only">Password</span>
						<input
							className="field-input pr-12"
							type={show ? "text" : "password"}
							autoComplete="current-password"
							placeholder="Password"
							value={password}
							onChange={(e) => setPassword(e.target.value)}
							required
						/>
						<button
							type="button"
							onClick={() => setShow(!show)}
							className="absolute right-2 top-1/2 grid size-9 -translate-y-1/2 place-items-center rounded-full text-zinc-400 hover:text-ink"
							aria-label={show ? "Hide password" : "Show password"}
						>
							{show ? <EyeOff className="size-[18px]" /> : <Eye className="size-[18px]" />}
						</button>
					</label>
				</div>

				{signedInAs && !error && (
					<div className="mt-4">
						<Banner kind="warning">
							{signedInAs} has no DeployOps role.{" "}
							<button type="button" className="font-medium underline" onClick={() => void logout().finally(() => window.location.reload())}>
								Sign out
							</button>{" "}
							and use a DeployOps account.
						</Banner>
					</div>
				)}
				{error && (
					<div className="mt-4">
						<Banner>{error}</Banner>
					</div>
				)}

				<Button type="submit" loading={busy} className="mt-6 w-full" icon={!busy && <ArrowRight className="size-[18px]" aria-hidden />}>
					Continue
				</Button>
				<p className="mt-10 text-center text-xs text-zinc-400">DeployOps · Massarie</p>
			</form>
		</main>
	);
}
