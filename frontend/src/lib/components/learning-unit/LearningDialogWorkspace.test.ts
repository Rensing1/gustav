import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const source = readFileSync(path.resolve(currentDir, "LearningDialogWorkspace.svelte"), "utf8");

describe("LearningDialogWorkspace", () => {
  it("implements pausing as navigation without a dialog mutation", () => {
    expect(source).toContain("Dialog pausieren");
    expect(source).toContain("/learning/courses/${encodeURIComponent(courseId)}");
    expect(source).not.toContain("/pause");
  });
});
