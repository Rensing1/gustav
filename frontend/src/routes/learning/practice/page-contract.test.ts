import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

describe("practice page contract", () => {
  it("offers stack selection and safe session controls", () => {
    const source = readFileSync("src/routes/learning/practice/+page.svelte", "utf8");
    expect(source).toContain("PracticeStackSelector");
    expect(source).toContain("PracticeSessionWorkspace");
    expect(source).not.toContain("teacher_context_md");
    expect(source).not.toContain("model_solution_md");
    expect(source).not.toContain("current_item.criteria");
  });

  it("restores the latest feedback without a feature flag or URL state", () => {
    const server = readFileSync("src/routes/learning/practice/+page.server.ts", "utf8");
    const page = readFileSync("src/routes/learning/practice/+page.svelte", "utf8");
    const sessionType = readFileSync("src/lib/types/practice.ts", "utf8");

    expect(server).toContain("current_item?.latest_attempt_id");
    expect(server).not.toContain("practice_enabled");
    expect(server).not.toContain('searchParams.get("attempt_id")');
    expect(server).not.toContain("?attempt_id=");
    expect(page).not.toContain("data.enabled");
    expect(page).toContain("PracticeSessionWorkspace");
    expect(sessionType).toContain("latest_attempt_id: string | null;");
    expect(sessionType).not.toContain("criteria: string[];");
  });
});
