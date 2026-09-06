// @vitest-environment node
import { describe, expect, it, vi } from "vitest";
import type { Browser } from "@playwright/test";

vi.mock("../e2e/support/e2e-env", () => ({ webBase: "https://app.localhost" }));
vi.mock("@playwright/test", () => ({ request: { newContext: vi.fn() } }));

import { request } from "@playwright/test";
import { newApiContext, newBrowserContext } from "../e2e/support/browser-context";

describe("trusted browser fixtures", () => {
  it("preserves browser options while refusing a runtime TLS bypass", () => {
    const create = vi.fn();
    const browser = { newContext: create } as unknown as Browser;
    newBrowserContext(browser, { hasTouch: true, ...{ ignoreHTTPSErrors: true } });
    expect(create).toHaveBeenCalledWith({
      baseURL: "https://app.localhost", hasTouch: true, ignoreHTTPSErrors: false
    });
  });

  it("keeps the same trust boundary for Keycloak API contexts", () => {
    newApiContext({ baseURL: "https://id.localhost", ...{ ignoreHTTPSErrors: true } });
    expect(request.newContext).toHaveBeenCalledWith({
      baseURL: "https://id.localhost", ignoreHTTPSErrors: false
    });
  });
});
