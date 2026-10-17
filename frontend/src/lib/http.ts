export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code: string,
    public fields: Record<string, string> = {},
    public requestId?: string,
  ) {
    super(message);
  }
}
export async function request<T>(
  path: string,
  token: string,
  init: RequestInit = {},
  responseType: "json" | "blob" = "json",
): Promise<T> {
  if (!token)
    throw new ApiError("Please sign in again.", 401, "UNAUTHENTICATED");
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(
      `${(import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "")}/api${path}`,
      { ...init, headers },
    );
  } catch (error) {
    if (init.signal?.aborted) throw error;
    throw new ApiError(
      "Could not reach the server. For a submitted action, check the saved result before trying again.",
      0,
      "NETWORK_ERROR",
    );
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const body = payload && typeof payload === "object" ? payload : {};
    throw new ApiError(
      body.detail ||
        `The server returned an error (${response.status}). Please try again later.`,
      response.status,
      body.code || "SERVER_ERROR",
      body.field_errors || {},
      body.request_id || response.headers.get("X-Request-ID"),
    );
  }
  if (response.status === 204) return undefined as T;
  return (
    responseType === "blob" ? response.blob() : response.json()
  ) as Promise<T>;
}
