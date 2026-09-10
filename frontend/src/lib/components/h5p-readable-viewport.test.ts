import { describe, expect, it } from "vitest";
import { readableRenderWidth, keepFocusVisible } from "./h5p-readable-viewport";

describe("H5P readable viewport", () => {
  it("derives real render width from the smallest actual content font", () => {
    expect(readableRenderWidth(600, [8, 12, 10], 320)).toBe(1200);
    expect(readableRenderWidth(600, [20, 24], 900)).toBe(900);
    expect(readableRenderWidth(600, [0, NaN, 8], 320)).toBe(1200);
    expect(readableRenderWidth(600, [], 320)).toBe(600);
  });

  it("scrolls only the task viewport to reveal keyboard focus", () => {
    const region = document.createElement("div"), target = document.createElement("button");
    region.append(target);
    region.getBoundingClientRect = () => ({ left: 10, right: 310, top: 20, bottom: 320 } as DOMRect);
    target.getBoundingClientRect = () => ({ left: 510, right: 610, top: 40, bottom: 80 } as DOMRect);
    keepFocusVisible(region, target);
    expect(region.scrollLeft).toBe(308);
    expect(region.scrollTop).toBe(0);
  });
});
