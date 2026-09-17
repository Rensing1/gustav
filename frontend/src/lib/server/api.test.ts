import { describe, expect, it, vi } from "vitest";
vi.mock("$env/dynamic/private", () => ({ env: { API_INTERNAL_BASE_URL: "http://backend.test" } }));
vi.mock("$app/server", () => ({ getRequestEvent: () => ({ request: new Request("https://app.example/action", { headers: { origin: "https://evil.example" } }) }) }));
import { backendRequest } from "./api";
const cookies = { get: (name: string) => name === "gustav_session" ? "opaque" : undefined };

describe("shared cookie transport", () => {
  it("forwards only the shared session and preserves the actual browser origin", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(null));
    await backendRequest(fetchMock, cookies as never, "/api/action", { method: "POST", includeSameOrigin: true });
    const headers = fetchMock.mock.calls[0][1]?.headers as Headers;
    expect(headers.get("cookie")).toBe("gustav_session=opaque");
    expect(headers.get("authorization")).toBeNull();
    expect(headers.get("origin")).toBe("https://evil.example");
  });
  it("never replays a write after an unauthorized response", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 401 }));
    const response = await backendRequest(fetchMock, cookies as never, "/api/action", { method: "POST", body: "draft", authRedirectPath: "/learning" });
    expect(response.status).toBe(401);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it("preserves infrastructure errors without a login redirect", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 503 }));
    expect((await backendRequest(fetchMock, cookies as never, "/api/read", { authRedirectPath: "/learning" })).status).toBe(503);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

it('returns a temporary error after one failed network attempt without replaying a write', async () => {
  const fetchMock = vi.fn<typeof fetch>().mockRejectedValue(new TypeError('network unavailable'));
  const response = await backendRequest(fetchMock, cookies as never, '/api/action', { method: 'POST', body: 'draft', authRedirectPath: '/learning' });
  expect(response.status).toBe(503);
  expect(fetchMock).toHaveBeenCalledTimes(1);
});
