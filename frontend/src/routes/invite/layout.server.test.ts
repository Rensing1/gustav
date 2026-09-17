import { describe, expect, it, vi } from "vitest";

import { load } from "./+layout.server";

describe("course invitation page security headers", () => {
  it("prevents browser caching and referrer disclosure for all invitation pages", () => {
    const setHeaders = vi.fn();

    load({ setHeaders, url: new URL("https://app.example/invite") } as never);

    expect(setHeaders).toHaveBeenCalledWith({
      "cache-control": "private, no-store",
      "referrer-policy": "no-referrer"
    });
  });
});

  it("keeps a verifiable origin on the explicit confirmation form", () => {
    const setHeaders = vi.fn();
    load({ setHeaders, url: new URL("https://app.example/invite/complete") } as never);
    expect(setHeaders).toHaveBeenCalledWith({ "cache-control": "private, no-store", "referrer-policy": "same-origin" });
  });
