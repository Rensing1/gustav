import { readFileSync } from "node:fs";

import { classifyBuildOutput } from "./build-output-policy.mjs";

const logPath = process.argv[2];
if (!logPath) {
  throw new Error("Build log path is required");
}

const result = classifyBuildOutput(readFileSync(logPath, "utf8"));
if (result.allowedWarnings.length > 0) {
  console.warn(`Allowed documented upstream warnings: ${result.allowedWarnings.length}`);
}
if (result.blockingWarnings.length > 0) {
  console.error("Frontend build warning gate failed:");
  for (const warning of result.blockingWarnings) {
    console.error(`- ${warning}`);
  }
  process.exit(1);
}
