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

  it("keeps polling until the attempt and session item form a settled view", () => {
    const page = readFileSync("src/routes/learning/practice/+page.svelte", "utf8");

    expect(page).toContain("practiceSessionNeedsPolling");
    expect(page).not.toContain('data.attempt?.status !== "pending"');
  });

  it("uses the full standard workspace and a container-driven selection layout", () => {
    const selector = readFileSync("src/lib/components/practice/PracticeStackSelector.svelte", "utf8");
    const styles = readFileSync("src/lib/styles/practice.css", "utf8");

    expect(selector).toContain('class="practice-selection__topics"');
    expect(selector).toContain('class="practice-selection__setup"');
    expect(styles).toMatch(/\.practice-page\s*\{[^}]*container-type:\s*inline-size;/s);
    expect(styles).toMatch(/\.practice-selection,[\s\S]*?width:\s*100%;/s);
    expect(styles).not.toContain("width: min(100%, 52rem);");
    expect(styles).toMatch(/@container\s*\(min-width:\s*64rem\)[\s\S]*?\.practice-selection__form\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+minmax\(18rem,\s*20rem\);/s);
  });

  it("uses a container-driven task workspace and adaptive summary metrics", () => {
    const workspace = readFileSync("src/lib/components/practice/PracticeSessionWorkspace.svelte", "utf8");
    const styles = readFileSync("src/lib/styles/practice.css", "utf8");

    expect(workspace).toContain('class="practice-session__main"');
    expect(workspace).toContain('class="practice-session__rail" aria-label="Sitzungsfortschritt"');
    expect(styles).toMatch(/@container\s*\(min-width:\s*64rem\)[\s\S]*?\.practice-session__layout\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+minmax\(18rem,\s*20rem\);/s);
    expect(styles).toMatch(/\.practice-summary__metrics\s*\{[^}]*repeat\(auto-fit,\s*minmax\(min\(12rem,\s*100%\),\s*1fr\)\)/s);
    expect(styles).toMatch(/\.practice-task-card__instruction\s*\{[^}]*max-width:\s*var\(--layout-reading-max\);/s);
  });
});
