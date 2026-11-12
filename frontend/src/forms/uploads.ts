/** Submission waits for private uploads before flushing the answers they produce. */
export class UploadTracker {
	private active = new Set<Promise<unknown>>();
	private onCount: (count: number) => void;
	constructor(onCount: (count: number) => void) { this.onCount = onCount; }
	async run<T>(upload: () => Promise<T>): Promise<T> {
		const task = upload();
		this.active.add(task);
		this.onCount(this.active.size);
		try { return await task; }
		finally { this.active.delete(task); this.onCount(this.active.size); }
	}
	async wait(): Promise<void> {
		while (this.active.size) await Promise.allSettled([...this.active]);
		// Let the field's await ctx.upload continuation enqueue its answer.
		await Promise.resolve();
	}
}
