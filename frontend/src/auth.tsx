import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "./lib/supabase";
import { request, ApiError } from "./lib/http";
import type { Me } from "./lib/types";

interface Auth {
  session: Session | null;
  me: Me | null;
  loading: boolean;
  error: unknown;
  workspace: string;
  setWorkspace: (id: string) => void;
  reload: () => void;
  signOut: () => Promise<void>;
  api: <T>(
    path: string,
    init?: RequestInit,
    type?: "json" | "blob",
  ) => Promise<T>;
}
const Context = createContext<Auth | null>(null);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(!supabase);
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>();
  const [workspace, setWorkspace] = useState("");
  const [version, setVersion] = useState(0);
  const identity = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (!supabase) return;
    const { data } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession((current) =>
        current?.access_token === next?.access_token ? current : next,
      );
      setReady(true);
      if (identity.current !== next?.user.id) {
        setMe(null);
        setWorkspace("");
        identity.current = next?.user.id;
      }
    });
    return () => data.subscription.unsubscribe();
  }, []);
  useEffect(() => {
    if (!session) {
      setMe(null);
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    request<Me>("/me", session.access_token, { signal: controller.signal })
      .then((data) => {
        if (controller.signal.aborted) return;
        setMe(data);
        setWorkspace((old) =>
          data.workspaces.some((w) => w.organization_id === old)
            ? old
            : data.workspaces[0]?.organization_id || "",
        );
      })
      .catch((err) => {
        if (!controller.signal.aborted) {
          setMe(null);
          setError(err);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [session, version]);
  const reload = useCallback(() => setVersion((v) => v + 1), []);
  const api = useCallback(
    async <T,>(path: string, init?: RequestInit, type?: "json" | "blob") => {
      const current = await supabase?.auth.getSession();
      if (current?.error) throw current.error;
      try {
        return await request<T>(
          path,
          current?.data.session?.access_token || "",
          init,
          type,
        );
      } catch (err) {
        if (
          err instanceof ApiError &&
          [401, 403].includes(err.status) &&
          ["UNAUTHENTICATED", "FORBIDDEN"].includes(err.code)
        )
          reload();
        throw err;
      }
    },
    [reload],
  );
  async function signOut() {
    const result = await supabase?.auth.signOut({ scope: "local" });
    if (result?.error) throw result.error;
    setSession(null);
    setMe(null);
    setWorkspace("");
  }
  return (
    <Context.Provider
      value={{
        session,
        me,
        loading: !ready || loading,
        error,
        workspace,
        setWorkspace,
        reload,
        api,
        signOut,
      }}
    >
      {children}
    </Context.Provider>
  );
}
export function useAuth() {
  const value = useContext(Context);
  if (!value) throw new Error("AuthProvider is required");
  return value;
}
