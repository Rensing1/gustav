import { accessSync, constants } from "node:fs";
import { chromium, webkit } from "@playwright/test";

const availableBrowsers = { chromium, webkit };
const requestedBrowsers = process.argv.slice(2);
const browserNames = requestedBrowsers.length ? requestedBrowsers : ["chromium"];

for (const browserName of browserNames) {
  const browser = availableBrowsers[browserName];
  if (!browser) {
    console.error(`Unknown Playwright browser: ${browserName}`);
    process.exit(1);
  }

  const executable = browser.executablePath();
  try {
    accessSync(executable, constants.X_OK);
  } catch {
    console.error(`Playwright ${browserName} is missing. Run \`make playwright-bootstrap\` first.`);
    process.exit(1);
  }

  console.log(`Playwright ${browserName} ready: ${executable}`);
}
