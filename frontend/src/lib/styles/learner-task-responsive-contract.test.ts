import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

describe("learner task responsive contract", () => {
  it("shows native and dialog task surfaces side by side on landscape iPads", () => {
    const learning = readFileSync(path.resolve(import.meta.dirname, "learning-unit.css"), "utf8");

    expect(learning).toMatch(
      /@container\s*\(min-width:\s*60rem\)\s*\{[\s\S]*?\.learner-task-workbench__desk\s*\{[\s\S]*?grid-template-columns:/s
    );
    expect(learning).toMatch(
      /@container\s+learning-dialog\s*\(min-width:\s*60rem\)\s*\{[\s\S]*?\.dialog-layout\s*\{[\s\S]*?grid-template-columns:/s
    );
  });

  it("keeps the no-container-query fallback aligned with a 1024px landscape viewport", () => {
    const learning = readFileSync(path.resolve(import.meta.dirname, "learning-unit.css"), "utf8");

    expect(learning).toMatch(
      /@supports not \(container-type:\s*inline-size\)[\s\S]*?@media \(min-width:\s*64rem\)[\s\S]*?\.learner-task-workbench__desk\s*\{[\s\S]*?grid-template-columns:/s
    );
  });
});
