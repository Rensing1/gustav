import { describe, expect, it, vi } from "vitest";

vi.mock("$env/dynamic/private", () => ({
  env: {
    API_INTERNAL_BASE_URL: "http://backend.test"
  }
}));

import { readAppSessionActive } from "./api";

class MemoryCookies {
  constructor(private readonly values: Map<string, string>) {}

  get(name: string): string | undefined {
    return this.values.get(name);
  }
}

describe("readAppSessionActive", () => {
  it("validates the existing app session by forwarding only the app session cookie", async () => {
    const cookies = new MemoryCookies(new Map([["gustav_session", "app-session-1"]]));
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ sub: "user-1" })));

    const active = await readAppSessionActive(fetchMock, cookies as never);

    expect(active).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith("http://backend.test/api/me", {
      method: "GET",
      headers: {
        cookie: "gustav_session=app-session-1"
      }
    });
  });

  it("does not attempt continuity without an app session cookie", async () => {
    const fetchMock = vi.fn<typeof fetch>();

    const active = await readAppSessionActive(fetchMock, new MemoryCookies(new Map()) as never);

    expect(active).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
