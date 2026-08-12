import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("practice summary route contract", () => {
  it("loads one durable ended session and renders the summary component", () => {
    const server = readFileSync("src/routes/learning/practice/sessions/[sessionId]/summary/+page.server.ts", "utf8");
    const page = readFileSync("src/routes/learning/practice/sessions/[sessionId]/summary/+page.svelte", "utf8");

    expect(server).toContain("/api/learning/practice/sessions/");
    expect(server).toContain('session.status !== "ended"');
    expect(page).toContain("PracticeSessionSummary");
    expect(page).not.toContain("criteria");
  });

  it("polls a stopped summary while accepted evaluations are pending", () => {
    const page = readFileSync("src/routes/learning/practice/sessions/[sessionId]/summary/+page.svelte", "utf8");
    expect(page).toContain("summary.pending_items");
    expect(page).toContain("invalidateAll");
  });
});
