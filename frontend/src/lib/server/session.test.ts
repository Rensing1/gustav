import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("$env/dynamic/private", () => ({
  env: {
    API_INTERNAL_BASE_URL: "http://backend.test",
    BFF_INTERNAL_SHARED_SECRET: "shared-test-secret",
    BFF_SESSION_TTL_SECONDS: "86400",
    FRONTEND_SESSION_COOKIE_NAME: "gustav_bff_session",
    KC_BASE_URL: "http://keycloak:8080",
    KC_CLIENT_ID: "gustav-web",
    KC_REALM: "gustav",
    ORIGIN: "https://app.localhost"
  }
}));

import { readFreshTokenSession } from "./session";

class MemoryCookies {
  store = new Map<string, string>();
  setCalls: Array<[string, string, object]> = [];
  deleteCalls: Array<[string, object]> = [];

  get(name: string): string | undefined {
    return this.store.get(name);
  }

  set(name: string, value: string, options: object): void {
    this.store.set(name, value);
    this.setCalls.push([name, value, options]);
  }

  delete(name: string, options: object): void {
    this.store.delete(name);
    this.deleteCalls.push([name, options]);
  }
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" }
  });
}

describe("readFreshTokenSession", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("refreshes an expired access token while the BFF session is still alive", async () => {
    const now = Math.floor(Date.now() / 1000);
    const cookies = new MemoryCookies();
    cookies.store.set("gustav_bff_session", "bff-session-1");

    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      const url = String(input);
      const method = init?.method || "GET";
      const headers = new Headers(init?.headers);

      if (url === "http://backend.test/backend-internal/app/bff-session" && method === "GET") {
        expect(headers.get("x-gustav-internal-secret")).toBe("shared-test-secret");
        return jsonResponse({
          session_id: "bff-session-1",
          access_token: "expired-access-token",
          refresh_token: "refresh-token-1",
          id_token: "id-token-1",
          expires_at: now - 30,
          session_expires_at: now + 3600
        });
      }

      if (url === "http://keycloak:8080/realms/gustav/protocol/openid-connect/token" && method === "POST") {
        return jsonResponse({
          access_token: "fresh-access-token",
          refresh_token: "refresh-token-2",
          id_token: "id-token-2",
          expires_in: 300
        });
      }

      if (url === "http://backend.test/backend-internal/app/bff-session" && method === "PATCH") {
        expect(headers.get("x-gustav-internal-secret")).toBe("shared-test-secret");
        return jsonResponse({
          session_id: "bff-session-1",
          access_token: "fresh-access-token",
          refresh_token: "refresh-token-2",
          id_token: "id-token-2",
          expires_at: now + 300,
          session_expires_at: now + 3600
        });
      }

      throw new Error(`unexpected request: ${method} ${url}`);
    });

    const session = await readFreshTokenSession(cookies as never, fetchMock);

    expect(session).toEqual({
      sessionId: "bff-session-1",
      accessToken: "fresh-access-token",
      refreshToken: "refresh-token-2",
      idToken: "id-token-2",
      expiresAt: now + 300,
      sessionExpiresAt: now + 3600
    });
    expect(cookies.deleteCalls).toHaveLength(0);
  });

  it("keeps a concurrently refreshed BFF session instead of deleting it after a stale refresh failure", async () => {
    const now = Math.floor(Date.now() / 1000);
    const cookies = new MemoryCookies();
    cookies.store.set("gustav_bff_session", "bff-session-race");
    let bffReads = 0;

    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      const url = String(input);
      const method = init?.method || "GET";

      if (url === "http://backend.test/backend-internal/app/bff-session" && method === "GET") {
        bffReads += 1;
        if (bffReads === 1) {
          return jsonResponse({
            session_id: "bff-session-race",
            access_token: "expired-access-token",
            refresh_token: "stale-refresh-token",
            id_token: "old-id-token",
            expires_at: now - 30,
            session_expires_at: now + 3600
          });
        }
        return jsonResponse({
          session_id: "bff-session-race",
          access_token: "fresh-access-token-from-other-request",
          refresh_token: "fresh-refresh-token",
          id_token: "fresh-id-token",
          expires_at: now + 300,
          session_expires_at: now + 3600
        });
      }

      if (url === "http://keycloak:8080/realms/gustav/protocol/openid-connect/token" && method === "POST") {
        return jsonResponse({ error: "invalid_grant" }, 400);
      }

      throw new Error(`unexpected request: ${method} ${url}`);
    });

    const session = await readFreshTokenSession(cookies as never, fetchMock, { forceRefresh: true });

    expect(session?.accessToken).toBe("fresh-access-token-from-other-request");
    expect(cookies.deleteCalls).toHaveLength(0);
    expect(fetchMock).not.toHaveBeenCalledWith(
      "http://backend.test/backend-internal/app/bff-session",
      expect.objectContaining({ method: "DELETE" })
    );
  });
});
