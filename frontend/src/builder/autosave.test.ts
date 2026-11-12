import { expect, it, vi } from "vitest";
import { Autosave } from "./autosave";
it("debounces edits and uses latest token, stops on conflict", async () => {
	vi.useFakeTimers();
	const save = vi.fn().mockResolvedValueOnce({modified: "2"}).mockRejectedValue(new Error("Changed by Jane, reload"));
	const a = new Autosave("1", save, () => {});
	a.edit("first"); a.edit("second"); await vi.advanceTimersByTimeAsync(1000);
	expect(save).toHaveBeenCalledTimes(1); expect(save).toHaveBeenLastCalledWith("second", "1");
	a.edit("third"); await vi.advanceTimersByTimeAsync(1000);
	expect(save).toHaveBeenLastCalledWith("third", "2"); expect(a.state).toBe("conflict"); expect(a.modifiedBy).toBe("Jane");
	a.edit("fourth"); await vi.advanceTimersByTimeAsync(1000); expect(save).toHaveBeenCalledTimes(2);
	a.dispose(); vi.useRealTimers();
});
it("supports StrictMode cleanup and reactivation", async () => {
	vi.useFakeTimers(); const save = vi.fn().mockResolvedValue({modified: "2"});
	const a = new Autosave("1", save, () => {}); a.dispose(); a.activate(); a.edit("after remount");
	await vi.advanceTimersByTimeAsync(1000); expect(save).toHaveBeenCalledTimes(1); a.dispose(); vi.useRealTimers();
});
it("flushes pending edits when leaving and preserves serialized order", async () => {
	const save = vi.fn().mockResolvedValue({modified: "2"}); const a = new Autosave("1", save, () => {});
	a.edit("latest"); await a.flush(); expect(save).toHaveBeenCalledWith("latest", "1"); expect(a.latestModified).toBe("2");
});
