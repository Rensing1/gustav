import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.WEB_BASE ?? "https://app.localhost";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL,
    trace: "retain-on-failure"
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    },
    {
      name: "webkit-ipad",
      testMatch: /(?:learner-task-(?:drafts|responsive)|ios-15-3-css-compatibility)\.spec\.ts/,
      use: { ...devices["iPad Pro 11 landscape"] }
    }
  ]
});
