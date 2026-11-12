import { afterEach, expect, it, vi } from "vitest";
import { AnswerQueue, mergeSaved } from "./queue";
import { ApiError } from "../lib/api";
import type { Answers } from "./types";
afterEach(() => vi.useRealTimers());
it("debounces changes into one save of only the changed fields", async () => { vi.useFakeTimers(); const save = vi.fn(async (c: Answers) => c); const q = new AnswerQueue({ save, onSaved: () => { }, onState: () => { } }); q.change("a", 1); q.change("b", 2); expect(save).not.toHaveBeenCalled(); await vi.advanceTimersByTimeAsync(800); expect(save).toHaveBeenCalledExactlyOnceWith({ a: 1, b: 2 }); });
it("newest value wins and a change during a save goes in the next save", async () => { let release: ((v: Answers) => void) | undefined; const batches: Answers[] = []; const q = new AnswerQueue({ save: c => { batches.push(c); return new Promise(r => { release = r; }); }, onSaved: () => { }, onState: () => { } }); q.change("a", 1); q.change("a", 2); const first = q.flush(); q.change("a", 3); const second = q.flush(); expect(batches).toEqual([{ a: 2 }]); release!({ a: 2 }); await new Promise(r => setTimeout(r, 0)); expect(batches).toEqual([{ a: 2 }, { a: 3 }]); release!({ a: 3 }); expect(await first).toBe(true); expect(await second).toBe(true); });
it("offline keeps the batch under newer changes", async () => { let reject: ((e: ApiError) => void) | undefined; const states: string[] = []; const q = new AnswerQueue({ save: () => new Promise((_, r) => { reject = r; }), onSaved: () => { }, onState: s => states.push(s) }); q.change("a", 1); const done = q.flush(); q.change("a", 2); reject!(new ApiError("offline", 0)); expect(await done).toBe(false); expect(q.pending).toEqual({ a: 2 }); expect(states.at(-1)).toBe("offline"); });
it("retries once without the fields the server rejected", async () => {
	const batches: Answers[] = []; const q = new AnswerQueue({
		save: async (c) => {
			batches.push(c); if (batches.length === 1)
				throw new ApiError("bad", 417, [{ field: "col", row: null, message: "bad" }]); return c;
		}, fieldOf: id => id === "col" ? "bad" : id, onSaved: () => { }, onState: () => { }
	}); q.change("bad", 1); q.change("good", 2); expect(await q.flush()).toBe(false); expect(batches).toEqual([{ bad: 1, good: 2 }, { good: 2 }]); expect(q.pending).toEqual({ bad: 1 });
});
it("dispose sends what is pending", async () => { const batches: Answers[] = []; const q = new AnswerQueue({ save: async (c) => { batches.push(c); return c; }, onSaved: () => { }, onState: () => { } }); q.change("a", 1); q.dispose(); await Promise.resolve(); expect(batches).toEqual([{ a: 1 }]); });
it("mergeSaved keeps typing done during the save", () => expect(mergeSaved({ a: 1, b: 2 }, { a: 3 })).toEqual({ a: 3, b: 2 }));

it("pending includes unsaved in-flight work for the unload guard", async () => { let finish: ((v: Answers) => void) | undefined; const q = new AnswerQueue({ save: () => new Promise(r => { finish = r; }), onSaved: () => { }, onState: () => { } }); q.change("a", 1); const done = q.flush(); expect(q.pending).toEqual({ a: 1 }); q.change("a", 2); expect(q.pending).toEqual({ a: 2 }); finish!({ a: 1 }); await Promise.resolve(); await Promise.resolve(); finish!({ a: 2 }); await done; expect(q.pending).toEqual({}); });
