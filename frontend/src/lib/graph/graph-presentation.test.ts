import { describe, expect, it } from "vitest";
import {
  graphAriaLabels,
  graphFocusNodes,
  orientationForViewport,
  remainingGraphHeight
} from "./graph-presentation";

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

  it("focuses a phase together with its module children", () => {
    const phase = { id: "phase:one", type: "phaseBand" };
    const firstModule = { id: "module:one", parentId: phase.id, type: "unitNode" };
    const secondModule = { id: "module:two", parentId: phase.id, type: "unitNode" };
    const otherPhase = { id: "phase:two", type: "phaseBand" };

    expect(graphFocusNodes(phase.id, [phase, firstModule, secondModule, otherPhase])).toEqual([
      phase,
      firstModule,
      secondModule
    ]);
    expect(graphFocusNodes(firstModule.id, [phase, firstModule, secondModule])).toEqual([firstModule]);
  });

  it("distinguishes orientation changes from ordinary viewport resizes", () => {
    expect(orientationForViewport(1024, 768)).toBe("landscape");
    expect(orientationForViewport(768, 1024)).toBe("portrait");
    expect(orientationForViewport(900, 900)).toBe("landscape");
  });
});
