import { expect, it, vi } from "vitest";
import { handle } from "./hooks.server";
const origin = "https://app.example";
it.each([
  [{}, 403],
  [{ origin: "https://evil.example", referer: `${origin}/invite` }, 403],
  [{ origin: "null" }, 403],
  [{ origin: `${origin}/invalid` }, 403],
  [{ origin }, 200],
  [{ referer: `${origin}/invite` }, 200]
])("validates actual provenance before any cookie-authenticated write (%j)", async (headers, status) => {
  const resolve = vi.fn(async () => new Response("ok"));
  const event = { url: new URL(`${origin}/invite/accept`), request: new Request(`${origin}/invite/accept`, { method: "POST", headers: headers as HeadersInit }), cookies: { get: () => "session" } };
  const response = await handle({ event, resolve } as never);
  expect(response.status).toBe(status);
  expect(resolve).toHaveBeenCalledTimes(status === 200 ? 1 : 0);
});

it.each(["/auth/logout", "/forgot-password"])("keeps a verifiable origin for the native form at %s", async (path) => {
  const event = { url: new URL(`${origin}${path}`), request: new Request(`${origin}${path}`) };
  const response = await handle({ event, resolve: async () => new Response("ok") } as never);
  expect(response.headers.get("referrer-policy")).toBe("same-origin");
});
