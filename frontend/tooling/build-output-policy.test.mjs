import assert from "node:assert/strict";
import test from "node:test";

import { classifyBuildOutput } from "./build-output-policy.mjs";

test("allows only documented D3 cycles", () => {
  const result = classifyBuildOutput("Circular dependency: node_modules/d3-selection/a.js -> node_modules/d3-transition/b.js");
  assert.equal(result.allowedWarnings.length, 1);
  assert.deepEqual(result.blockingWarnings, []);
});

test("allows only XYFlow's exact Svelte SSR unused-import false positive", () => {
  const known = classifyBuildOutput('"handleConnectionChange" is imported from external module "@xyflow/system" but never used in "node_modules/@xyflow/svelte/dist/lib/hooks/useNodeConnections.svelte.js" and "node_modules/@xyflow/svelte/dist/lib/components/Handle/Handle.svelte".');
  const unknown = classifyBuildOutput('"handleConnectionChange" is imported from external module "@xyflow/system" but never used in "src/example.js".');
  assert.equal(known.allowedWarnings.length, 1);
  assert.equal(unknown.blockingWarnings.length, 1);
});

test("blocks unused imports, large chunks, unknown and mixed cycles", () => {
  const result = classifyBuildOutput(`
"unused" is imported from external module "example" but never used.
Some chunks are larger than 500 kB after minification.
Circular dependency: node_modules/example/a.js -> node_modules/example/b.js
Circular dependency: node_modules/d3-selection/a.js -> node_modules/example/b.js
`);
  assert.equal(result.blockingWarnings.length, 4);
});
