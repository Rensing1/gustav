import { assertNoCascadeLayers } from "./css-compatibility.mjs";

const assetDirectory = process.argv[2];

if (!assetDirectory) {
  throw new Error("Usage: node tooling/check-css-compatibility.mjs <client-asset-directory>");
}

await assertNoCascadeLayers(assetDirectory);
