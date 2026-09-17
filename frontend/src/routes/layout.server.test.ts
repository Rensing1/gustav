import { expect, it, vi } from "vitest";
const mock = vi.hoisted(() => ({ bootstrap: vi.fn().mockRejectedValue(new Error("identity provider unavailable")) }));
vi.mock("$lib/server/api", () => ({ readTypedJsonOrNull: mock.bootstrap }));
import { load } from "./+layout.server";
it.each(["/auth/problem", "/auth/logout", "/auth/logout/success"])("keeps %s reachable without refreshing the session", async (path) => {
  const result = await load({ url: new URL(`https://app.example${path}`), cookies: { get: () => undefined }, fetch: vi.fn() } as never);
  expect(result).toMatchObject({ bootstrap: null });
  expect(mock.bootstrap).not.toHaveBeenCalled();
});
