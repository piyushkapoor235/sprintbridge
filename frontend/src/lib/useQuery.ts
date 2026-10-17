import { useEffect, useState } from "react";
import { useAuth } from "../auth";
export function useQuery<T>(path: string | null) {
  const { api } = useAuth();
  const [state, setState] = useState<{
    path: string | null;
    data?: T;
    error?: unknown;
  }>({ path: null });
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(Boolean(path));
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    setLoading(true);
    // A reload of the same path keeps showing the current data (no flicker after an action);
    // a different path never shows another view's data.
    setState((prev) => (prev.path === path ? { path, data: prev.data } : { path }));
    api<T>(path, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setState({ path, data });
      })
      .catch((error) => {
        if (!controller.signal.aborted) setState({ path, error });
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [path, revision, api]);
  return {
    data: state.path === path ? state.data : undefined,
    error: state.path === path ? state.error : undefined,
    loading: Boolean(path) && (loading || state.path !== path),
    reload: () => setRevision((v) => v + 1),
  };
}
