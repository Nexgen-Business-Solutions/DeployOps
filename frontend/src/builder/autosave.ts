export type SaveState = "saved" | "waiting" | "saving" | "conflict" | "error";
export class Autosave<T> {
	state: SaveState = "saved";
	modifiedBy = "";
	error = "";
	private pending?: T;
	private timer?: ReturnType<typeof setTimeout>;
	private running?: Promise<void>;
	private disposed = false;
	private modified: string;
	private save: (value: T, modified: string) => Promise<{modified: string}>;
	private notify: () => void;
	constructor(modified: string, save: (value: T, modified: string) => Promise<{modified: string}>, notify: () => void) {this.modified = modified; this.save = save; this.notify = notify;}
	edit(value: T) {
		if (this.disposed || this.state === "conflict") return;
		this.pending = value; clearTimeout(this.timer); this.state = "waiting"; this.notify();
		this.timer = setTimeout(() => {void this.flush().catch(() => {});}, 1000);
	}
	async flush(): Promise<void> {
		clearTimeout(this.timer);
		if (this.running) {await this.running; return this.flush();}
		if (this.state === "conflict") throw new Error(`Changed by ${this.modifiedBy}, reload`);
		if (this.pending === undefined || this.disposed) return;
		const value = this.pending; this.pending = undefined; this.state = "saving"; this.notify();
		this.running = (async () => {
			try {const result = await this.save(value, this.modified); this.modified = result.modified; this.state = "saved"; this.error = "";}
			catch (error) {
				this.error = error instanceof Error ? error.message : String(error);
				const match = this.error.match(/Changed by (.*), reload/i);
				this.state = match ? "conflict" : "error"; this.modifiedBy = match?.[1] ?? "";
				if (this.state === "conflict") this.pending = undefined;
				else if (this.pending === undefined) this.pending = value;
				throw error;
			} finally {this.running = undefined; this.notify();}
		})();
		await this.running;
		if (this.pending !== undefined) await this.flush();
	}
	get latestModified() {return this.modified;}
	activate() {this.disposed = false;}
	dispose() {this.disposed = true; clearTimeout(this.timer);}
}
