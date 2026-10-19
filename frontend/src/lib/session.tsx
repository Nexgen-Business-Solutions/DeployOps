import { createContext, useContext } from "react";

import type { Me } from "./types";

export const SessionContext = createContext<Me | null>(null);

export function useSession(): Me {
	const me = useContext(SessionContext);
	if (!me) throw new Error("useSession used outside a logged-in screen");
	return me;
}
