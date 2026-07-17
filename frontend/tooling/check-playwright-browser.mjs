import { accessSync, constants } from "node:fs";
import { chromium } from "@playwright/test";

const executable = chromium.executablePath();

try {
  accessSync(executable, constants.X_OK);
} catch {
  console.error(
    "Playwright Chromium is missing. Run `make playwright-bootstrap` before `make test-visual-smoke`."
  );
  process.exit(1);
}

console.log(`Playwright Chromium ready: ${executable}`);
