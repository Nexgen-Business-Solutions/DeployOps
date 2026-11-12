import { ApiError } from "../lib/api";
import type { Answers } from "./types";
export type SaveState = "idle" | "saving" | "saved" | "offline" | "error";
type Options = {
	save: (changes: Answers) => Promise<Answers>;
	onSaved: (server: Answers, stillPending: Answers) => void;
	onState: (state: SaveState, error: ApiError | null) => void;
	fieldOf?: (errorField: string) => string;
	delayMs?: number;
};
export function mergeSaved(server: Answers, pending: Answers): Answers { return { ...server, ...pending }; }
export class AnswerQueue {
	private opts: Options;
	private changes: Answers = {};
	private inFlight: Answers = {};
	private timer: ReturnType<typeof setTimeout> | undefined;
	private running: Promise<boolean> | null = null;
	constructor(opts: Options) { this.opts = opts; }
	get pending(): Answers { return { ...this.inFlight, ...this.changes }; }
	change(fieldId: string, value: unknown): void {
		this.changes[fieldId] = value;
		clearTimeout(this.timer);
		this.timer = setTimeout(() => { void this.flush(); }, this.opts.delayMs ?? 800);
	}
	async flush(): Promise<boolean> {
		clearTimeout(this.timer);
		if (this.running) {
			const ok = await this.running;
			if (!ok)
				return false;
			return this.flush();
		}
		if (!Object.keys(this.changes).length)
			return true;
		this.running = this.send();
		const ok = await this.running;
		this.running = null;
		this.inFlight = {};
		return ok ? this.flush() : false;
	}
	private async send(): Promise<boolean> {
		const batch = this.changes;
		this.inFlight = batch;
		this.changes = {};
		this.opts.onState("saving", null);
		try {
			const server = await this.opts.save(batch);
			this.opts.onSaved(server, { ...this.changes });
			this.opts.onState("saved", null);
			return true;
		}
		catch (e) {
			const error = e instanceof ApiError ? e : new ApiError(String(e), 500);
			const rejected = new Set((error.formErrors ?? []).flatMap(e => e.field ? [this.opts.fieldOf?.(e.field) ?? e.field] : []));
			const good = Object.fromEntries(Object.entries(batch).filter(([id]) => !rejected.has(id)));
			const bad = Object.fromEntries(Object.entries(batch).filter(([id]) => rejected.has(id)));
			if (Object.keys(bad).length && Object.keys(good).length) {
				this.changes = { ...bad, ...this.changes };
				try {
					const server = await this.opts.save(good);
					this.opts.onSaved(server, { ...this.changes });
				}
				catch (retryError) {
					this.changes = { ...good, ...this.changes };
					const retry = retryError instanceof ApiError ? retryError : new ApiError(String(retryError), 500);
					this.opts.onState(retry.status === 0 ? "offline" : "error", retry);
					return false;
				}
			}
			else
				this.changes = { ...batch, ...this.changes };
			this.opts.onState(error.status === 0 ? "offline" : "error", error);
			return false;
		}
	}
	dispose(): void { clearTimeout(this.timer); void this.flush(); }
}
