import { describe, expect, it, vi } from "vitest";

import { assertChunkSizeLimit, handleBuildWarning } from "./build-warning-gate";

describe("frontend build warning gate", () => {
  it("keeps only the documented all-D3 circular dependencies visible", () => {
    const showWarning = vi.fn();

    handleBuildWarning({
      code: "CIRCULAR_DEPENDENCY",
      message: "known D3 cycle",
      ids: [
        "/app/node_modules/d3-selection/src/selection/index.js",
        "/app/node_modules/d3-transition/src/transition/index.js"
      ]
    }, showWarning);

    expect(showWarning).toHaveBeenCalledOnce();
  });

  it("blocks unknown cycles and unknown unused external imports", () => {
    const showWarning = vi.fn();

    expect(() => handleBuildWarning({
      code: "CIRCULAR_DEPENDENCY",
      message: "unknown cycle",
      ids: ["/app/node_modules/example-a/index.js", "/app/node_modules/example-b/index.js"]
    }, showWarning)).toThrow("unknown cycle");
    expect(() => handleBuildWarning({
      code: "UNUSED_EXTERNAL_IMPORT",
      message: "unused import"
    }, showWarning)).toThrow("unused import");
  });

  it("keeps XYFlow's exact Svelte SSR false positive visible", () => {
    const showWarning = vi.fn();
    handleBuildWarning({
      code: "UNUSED_EXTERNAL_IMPORT",
      message: '"handleConnectionChange" is imported from external module "@xyflow/system" but never used in "node_modules/@xyflow/svelte/dist/lib/hooks/useNodeConnections.svelte.js" and "node_modules/@xyflow/svelte/dist/lib/components/Handle/Handle.svelte".'
    }, showWarning);
    expect(showWarning).toHaveBeenCalledOnce();
  });

  it("blocks JavaScript chunks above 500 kB but ignores worker assets", () => {
    expect(() => assertChunkSizeLimit({ "large.js": { type: "chunk", code: "x".repeat(500_001) } })).toThrow("large.js");
    expect(() => assertChunkSizeLimit({ "worker.js": { type: "asset", source: "x".repeat(500_001) } })).not.toThrow();
  });

});
