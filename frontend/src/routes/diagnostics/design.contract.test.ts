import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const source = (relative: string) => readFileSync(fileURLToPath(new URL(relative, import.meta.url)), "utf8");

describe("teaching overview design contract", () => {
  it("uses shared surfaces instead of a separate diagnostics palette", () => {
    for (const route of ["./courses/[courseId]/+page.svelte", "./learners/[studentSub]/+page.svelte"]) {
      const page = source(route);
      expect(page).toContain("workspace-panel");
      expect(page).not.toMatch(/#[0-9a-f]{3,8}\b/i);
      expect(page).not.toContain("ghost-link");
      const loader = source(route.replace("+page.svelte", "+page.server.ts"));
      expect(loader).toContain("hidePageHeading: true");
    }
    expect(source("./courses/[courseId]/+page.svelte")).toContain('aria-label="Kursmatrix"');
    expect(source("../../lib/styles/teaching-workspace.css")).toContain(".workspace-panel.workspace-panel--flat {");
    const live = source("../live/+page.svelte");
    expect(live).not.toContain("linear-gradient");
  });
  it("offers a concrete course choice and hides internal membership identifiers", () => {
    expect(source("./+page.svelte")).toContain("Kursmatrix öffnen");
    expect(source("./+page.server.ts")).toContain("/api/teaching/views/courses?");
    const members = source("../teaching/courses/[courseId]/members/+page.svelte");
    expect(members).not.toContain("{member.sub}");
    expect(members).not.toContain("SvelteKit");
    expect(members).toContain("workspace-panel--flat");
  });
  it("keeps live tables in a named scroll region and actions at touch size", () => {
    const live = source("../live/+page.svelte");
    expect(live).toContain('role="region" aria-label="Klassenübersicht"');
    expect(live).toContain("task.task_position");
    const styles = source("../../lib/styles/teaching-workspace.css");
    const tab = styles.slice(styles.indexOf(".workspace-tab {"), styles.indexOf(".workspace-overview-grid"));
    expect(tab).toContain("var(--layout-control-min)");
    expect(tab).not.toContain("255, 250, 243");
  });
});
