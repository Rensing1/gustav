import { describe, expect, it } from "vitest";
import { graphAriaLabels, remainingGraphHeight } from "./graph-presentation";

describe("shared graph presentation", () => {
  it("uses the remaining screen height without changing graph coordinates", () => {
    expect(remainingGraphHeight(900, 240)).toBe(644);
    expect(remainingGraphHeight(844, 540)).toBe(288);
    expect(remainingGraphHeight(400, 390)).toBe(240);
  });
  it("names standard controls in German", () => {
    expect(graphAriaLabels["controls.zoomIn.ariaLabel"]).toBe("Vergrößern");
    expect(graphAriaLabels["controls.zoomOut.ariaLabel"]).toBe("Verkleinern");
    expect(graphAriaLabels["controls.interactive.ariaLabel"]).toBe("Knotenbearbeitung umschalten");
  });
});
