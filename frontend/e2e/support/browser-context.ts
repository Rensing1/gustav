import { request, type Browser, type BrowserContextOptions } from "@playwright/test";

import { webBase } from "./e2e-env";

/** Keep every explicitly created context on the same trusted TLS boundary. */
export function newBrowserContext(
  browser: Browser,
  options: Omit<BrowserContextOptions, "ignoreHTTPSErrors"> = {}
) {
  return browser.newContext({ baseURL: webBase, ...options, ignoreHTTPSErrors: false });
}

export function newApiContext(
  options: Omit<NonNullable<Parameters<typeof request.newContext>[0]>, "ignoreHTTPSErrors"> = {}
) {
  return request.newContext({ ...options, ignoreHTTPSErrors: false });
}
