import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const routesDir = path.dirname(fileURLToPath(import.meta.url));

const protectedPages = [
  "learning/+page.server.ts",
  "learning/kummerkasten/+page.server.ts",
  "learning/courses/[courseId]/+page.server.ts",
  "learning/courses/[courseId]/units/[unitId]/+page.server.ts",
  "profile/+page.server.ts",
  "teaching/+page.server.ts",
  "teaching/kummerkasten/+page.server.ts",
  "teaching/courses/+page.server.ts",
  "teaching/courses/[courseId]/+page.server.ts",
  "teaching/courses/[courseId]/members/+page.server.ts",
  "teaching/units/+page.server.ts",
  "teaching/units/[unitId]/+page.server.ts",
  "teaching/units/[unitId]/nodes/[nodeId]/+page.server.ts",
  "diagnostics/+page.server.ts",
  "diagnostics/courses/[courseId]/+page.server.ts",
  "diagnostics/learners/[studentSub]/+page.server.ts",
  "live/+page.server.ts",
  "live/courses/[courseId]/+page.server.ts",
  "live/courses/[courseId]/units/[unitId]/+page.server.ts",
  "ui-lab/+page.server.ts"
];

describe("protected Svelte page bootstrap contract", () => {
  it("uses the parent layout bootstrap in page loads instead of refetching session-bootstrap", () => {
    for (const relativePath of protectedPages) {
      const source = readFileSync(path.resolve(routesDir, relativePath), "utf8");
      const loadStart = source.indexOf("export const load");
      const loadSource = loadStart >= 0 ? source.slice(loadStart, source.indexOf("};", loadStart) + 2) : "";

      expect(loadSource, relativePath).toContain("parent");
      expect(loadSource, relativePath).toMatch(/requireParent(Session|Space)Bootstrap/);
      expect(loadSource, relativePath).not.toContain("requireSessionBootstrap(");
      expect(loadSource, relativePath).not.toContain("requireSpaceBootstrap(");
    }
  });
});
