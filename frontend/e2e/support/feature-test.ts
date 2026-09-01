import { execFile } from "node:child_process";
import { resolve } from "node:path";
import { promisify } from "node:util";

import { expect, test as base } from "@playwright/test";


const execFileAsync = promisify(execFile);
const projectRoot = resolve(process.cwd(), "..");

export const test = base.extend<{ e2eCleanup: void }>({
  e2eCleanup: [
    async ({}, use) => {
      try {
        await use();
      } finally {
        if (process.env.E2E_STATE_PATH) {
          await execFileAsync(
            resolve(projectRoot, ".venv/bin/python"),
            ["-m", "backend.tools.feature_acceptance", "cleanup", "--keep-manifest"],
            { cwd: projectRoot, env: process.env, maxBuffer: 1024 * 1024 }
          );
        }
      }
    },
    { auto: true }
  ]
});

export { expect };
export type {
  APIRequestContext,
  Browser,
  BrowserContext,
  Page,
  TestInfo
} from "@playwright/test";
