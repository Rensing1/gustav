import { describe, expect, it } from "vitest";
import { readViewport, writeViewport } from "./viewport-memory";

describe("tab-local graph viewport memory", () => {
  it("restores finite camera coordinates without mixing graph keys", () => {
    sessionStorage.clear();
    writeViewport(sessionStorage, "teacher:unit-1", { x: -42, y: 19, zoom: 0.5 });
    expect(readViewport(sessionStorage, "teacher:unit-1")).toEqual({ x: -42, y: 19, zoom: 0.5 });
    expect(readViewport(sessionStorage, "teacher:unit-2")).toBeNull();
  });
  it.each(['not-json', '{}', '{"x":0,"y":0,"zoom":0}', '{"x":"0","y":0,"zoom":1}', '{"x":0,"y":0,"zoom":9}'])("ignores invalid stored camera %s", (raw) => {
    sessionStorage.setItem("camera", raw);
    expect(readViewport(sessionStorage, "camera")).toBeNull();
  });
  it("treats unavailable storage as optional", () => {
    const storage = { getItem() { throw Error("denied"); }, setItem() { throw Error("denied"); } };
    expect(readViewport(storage, "camera")).toBeNull();
    expect(() => writeViewport(storage, "camera", { x: 0, y: 0, zoom: 1 })).not.toThrow();
  });
});
