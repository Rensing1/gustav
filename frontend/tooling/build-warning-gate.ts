import type { LoggingFunction, RollupLog } from "rollup";
import type { Plugin } from "vite";

const MAX_CHUNK_BYTES = 500_000;
const ALLOWED_D3_MODULE = /node_modules\/d3-(selection|interpolate|transition)\//;
const ALLOWED_XYFLOW_SSR_IMPORT = /"handleConnectionChange".*"@xyflow\/system".*node_modules\/@xyflow\/svelte\/dist\/lib\/hooks\/useNodeConnections\.svelte\.js.*node_modules\/@xyflow\/svelte\/dist\/lib\/components\/Handle\/Handle\.svelte/;

type BundleEntry = { type: "chunk"; code: string } | { type: "asset"; source: string | Uint8Array };

function cycleModules(warning: RollupLog): string[] {
  if (warning.ids?.length) {
    return warning.ids;
  }
  return warning.message.match(/[^\s]+node_modules\/[^\s]+/g) ?? [];
}

/** Allow only cycles whose complete module chain belongs to the known D3 trio. */
function isAllowedD3Cycle(warning: RollupLog): boolean {
  const modules = cycleModules(warning);
  return modules.length > 0 && modules.every((moduleId) => ALLOWED_D3_MODULE.test(moduleId));
}

/** Keep documented D3 warnings visible and fail on newly actionable warnings. */
export function handleBuildWarning(warning: RollupLog, showWarning: LoggingFunction): void {
  if (warning.code === "CIRCULAR_DEPENDENCY") {
    if (isAllowedD3Cycle(warning)) {
      showWarning(warning);
      return;
    }
    throw new Error(`[build-warning-gate] ${warning.message}`);
  }
  if (warning.code === "UNUSED_EXTERNAL_IMPORT") {
    if (ALLOWED_XYFLOW_SSR_IMPORT.test(warning.message)) {
      showWarning(warning);
      return;
    }
    throw new Error(`[build-warning-gate] ${warning.message}`);
  }
  showWarning(warning);
}

/** Fail before publishing when a minified JavaScript chunk exceeds 500 kB. */
export function assertChunkSizeLimit(bundle: Record<string, BundleEntry>): void {
  for (const [fileName, output] of Object.entries(bundle)) {
    if (output.type === "chunk" && Buffer.byteLength(output.code, "utf8") > MAX_CHUNK_BYTES) {
      throw new Error(`[build-warning-gate] ${fileName} exceeds 500 kB`);
    }
  }
}

export function buildWarningGate(): Plugin {
  return {
    name: "gustav-build-warning-gate",
    apply: "build",
    generateBundle(_outputOptions, bundle) {
      assertChunkSizeLimit(bundle);
    }
  };
}
