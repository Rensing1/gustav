import { afterEach, describe, expect, it, vi } from "vitest";
import { browserUUID } from "./browser-uuid";

afterEach(() => vi.unstubAllGlobals());

describe("secure browser UUIDs", () => {
  it("prefers the native implementation", () => {
    const randomUUID = vi.fn(() => "123e4567-e89b-42d3-a456-426614174000");
    vi.stubGlobal("crypto", { randomUUID });
    expect(browserUUID()).toBe("123e4567-e89b-42d3-a456-426614174000");
    expect(randomUUID).toHaveBeenCalledOnce();
  });
  it("uses secure random bytes and sets the UUID version and variant", () => {
    const getRandomValues = vi.fn((bytes: Uint8Array) => bytes.fill(255));
    vi.stubGlobal("crypto", { getRandomValues });
    expect(browserUUID()).toBe("ffffffff-ffff-4fff-bfff-ffffffffffff");
    expect(getRandomValues).toHaveBeenCalledOnce();
  });
  it("fails closed when secure randomness is unavailable", () => {
    vi.stubGlobal("crypto", undefined);
    expect(() => browserUUID()).toThrow("Dieser Browser kann keine sicheren Kennungen erzeugen.");
  });
});
