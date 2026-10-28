import { useCallback, useEffect, useState } from "react";

import { ApiError, get } from "./api";

/** Load one GET method; `reload` refetches. A 403 means the session ended. */
export function useApi<T>(method: string, args: Record<string, unknown> = {}) {
	const key = JSON.stringify(args);
	const [data, setData] = useState<T | null>(null);
	const [error, setError] = useState<ApiError | null>(null);
	const [loading, setLoading] = useState(true);

	const load = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			setData(await get<T>(method, JSON.parse(key) as Record<string, unknown>));
		} catch (e) {
			setError(e instanceof ApiError ? e : new ApiError(String(e), 0));
		} finally {
			setLoading(false);
		}
	}, [method, key]);

	useEffect(() => {
		void load();
	}, [load]);

	return { data, error, loading, reload: load, setData };
}
