import { describe, expect, it, vi } from "vitest";

import { load } from "./+layout.server";

describe("course invitation page security headers", () => {
  it("prevents browser caching and referrer disclosure for all invitation pages", () => {
    const setHeaders = vi.fn();

    load({ setHeaders } as never);

    expect(setHeaders).toHaveBeenCalledWith({
      "cache-control": "private, no-store",
      "referrer-policy": "no-referrer"
    });
  });
});
