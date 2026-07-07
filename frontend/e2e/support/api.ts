import { expect, type APIResponse } from "@playwright/test";

import { webBase } from "./e2e-env";

export function apiHeaders(refererPath = "/teaching/units") {
  return {
    origin: webBase,
    referer: `${webBase}${refererPath}`,
    "content-type": "application/json"
  };
}

export async function expectApiOk(response: APIResponse, expectedStatus?: number): Promise<void> {
  if (expectedStatus !== undefined) {
    expect(response.status(), await response.text()).toBe(expectedStatus);
    return;
  }
  expect(response.ok(), await response.text()).toBe(true);
}
