import { afterEach, expect, test, vi } from "vitest";
import { request, ApiError } from "./http";
afterEach(() => vi.unstubAllGlobals());
test("sends bearer auth and JSON without retrying a failed mutation", async () => {
  const fetcher = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({
        code: "ALREADY_APPLIED",
        detail: "Already applied",
        field_errors: {},
        request_id: "req-1234",
      }),
      { status: 409 },
    ),
  );
  vi.stubGlobal("fetch", fetcher);
  await expect(
    request("/applications", "token", { method: "POST", body: "{}" }),
  ).rejects.toMatchObject({ code: "ALREADY_APPLIED", requestId: "req-1234" });
  expect(fetcher).toHaveBeenCalledTimes(1);
  const headers = fetcher.mock.calls[0][1].headers as Headers;
  expect(headers.get("Authorization")).toBe("Bearer token");
  expect(headers.get("Content-Type")).toBe("application/json");
});
test("does not set a multipart boundary and supports CSV blobs", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue(
      new Response("name\nAsha", { headers: { "Content-Type": "text/csv" } }),
    );
  vi.stubGlobal("fetch", fetcher);
  const result = await request(
    "/upload",
    "token",
    { method: "POST", body: new FormData() },
    "blob",
  );
  expect(result).toBeInstanceOf(Blob);
  expect(fetcher.mock.calls[0][1].headers.has("Content-Type")).toBe(false);
});
test("non-JSON failures remain actionable", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response("<html>Bad gateway</html>", { status: 502 }),
      ),
  );
  await expect(request("/me", "token")).rejects.toBeInstanceOf(ApiError);
});
test("refuses unauthenticated requests before network access", async () => {
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  await expect(request("/me", "")).rejects.toMatchObject({ status: 401 });
  expect(fetcher).not.toHaveBeenCalled();
});

test("null JSON error responses still produce a controlled API error", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response("null", { status: 503 })),
  );
  await expect(request("/me", "token")).rejects.toMatchObject({
    status: 503,
    code: "SERVER_ERROR",
  });
});
