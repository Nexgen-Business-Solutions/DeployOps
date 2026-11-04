import { createContext, useContext } from "react";

import { ApiError } from "./api";
import type { Card } from "./types";

/** The shell's shared data: the checklists with counts, loaded once for the sidebar and Overview. */
export type Shell = { cards: Card[] | null; error: ApiError | null; loading: boolean };

export const ShellContext = createContext<Shell | null>(null);

export function useShell(): Shell {
	const shell = useContext(ShellContext);
	if (!shell) throw new Error("useShell used outside the app shell");
	return shell;
}

/** True on screens inside the app shell (header and sidebar); the standalone home grid is not. */
export function useInShell(): boolean {
	return useContext(ShellContext) !== null;
}
