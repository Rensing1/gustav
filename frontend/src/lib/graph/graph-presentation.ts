import type { AriaLabelConfig } from "@xyflow/system";

/** Labels describe available graph interactions, never internal identifiers. */
export const graphAriaLabels: Partial<AriaLabelConfig> = {
  "controls.ariaLabel": "Graphansicht steuern",
  "controls.zoomIn.ariaLabel": "Vergrößern",
  "controls.zoomOut.ariaLabel": "Verkleinern",
  "controls.fitView.ariaLabel": "Gesamtansicht",
  "controls.interactive.ariaLabel": "Knotenbearbeitung umschalten",
  "node.a11yDescription.default": "Mit Eingabe oder Leertaste auswählen, mit Escape abbrechen.",
  "node.a11yDescription.keyboardDisabled": "Mit Eingabe oder Leertaste auswählen. Mit den Pfeiltasten verschieben, mit Escape abbrechen.",
  "node.a11yDescription.ariaLiveMessage": ({ x, y }) => `Knoten verschoben. Position: ${x}, ${y}.`,
  "edge.a11yDescription.default": "Verbindung mit Eingabe oder Leertaste auswählen, mit Escape abbrechen.",
  "minimap.ariaLabel": "Kleine Graphübersicht",
  "handle.ariaLabel": "Verbindungsanschluss"
};

export function remainingGraphHeight(screenHeight: number, top: number): number {
  // Extremely short screens retain a usable canvas and ordinary page scrolling.
  return Math.max(240, screenHeight - Math.max(0, top) - 16);
}

/** Measure page chrome instead of assuming equal header heights for both roles. */
export function fitGraphToScreen(node: HTMLElement) {
  let frame = 0;
  const update = () => {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => {
      const visibleTop = node.getBoundingClientRect().top;
      node.style.setProperty("--graph-available-height", `${remainingGraphHeight(window.innerHeight, visibleTop)}px`);
    });
  };
  const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(update);
  // Page height changes include opening/closing the context bar. Height writes
  // settle after one extra callback because the calculated value is unchanged.
  observer?.observe(document.body);
  window.addEventListener("resize", update);
  window.addEventListener("scroll", update, { passive: true });
  update();
  return { destroy() { observer?.disconnect(); cancelAnimationFrame(frame); window.removeEventListener("resize", update); window.removeEventListener("scroll", update); } };
}
