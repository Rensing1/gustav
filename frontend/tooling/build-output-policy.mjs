const ALLOWED_D3_CYCLE = /node_modules\/d3-(selection|interpolate|transition)\//;
const ALLOWED_XYFLOW_SSR_IMPORT = /"handleConnectionChange".*"@xyflow\/system".*node_modules\/@xyflow\/svelte\/dist\/lib\/hooks\/useNodeConnections\.svelte\.js.*node_modules\/@xyflow\/svelte\/dist\/lib\/components\/Handle\/Handle\.svelte/;

/** Classify warnings from both Vite and adapter-node's final Rollup pass. */
export function classifyBuildOutput(output) {
  const allowedWarnings = [];
  const blockingWarnings = [];

  for (const line of output.split(/\r?\n/)) {
    if (line.includes("Circular dependency:")) {
      const modules = line.match(/node_modules\/[^\s]+/g) ?? [];
      (modules.length > 0 && modules.every((moduleId) => ALLOWED_D3_CYCLE.test(moduleId))
        ? allowedWarnings
        : blockingWarnings).push(line.trim());
      continue;
    }
    if (line.includes("but never used")) {
      (ALLOWED_XYFLOW_SSR_IMPORT.test(line) ? allowedWarnings : blockingWarnings).push(line.trim());
      continue;
    }
    if (line.includes("Some chunks are larger than 500 kB")) {
      blockingWarnings.push(line.trim());
    }
  }

  return { allowedWarnings, blockingWarnings };
}
