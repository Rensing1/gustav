import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("teacher work starter route contract", () => {
  const currentDir = path.dirname(fileURLToPath(import.meta.url));
  const pageSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

  it("renders only the two direct work paths with shared primitives", () => {
    expect(pageSource).toContain('import PageActionHead from "$lib/components/ui/PageActionHead.svelte";');
    expect(pageSource).toContain('import QuietList from "$lib/components/ui/QuietList.svelte";');
    expect(pageSource).toContain('import QuietListEntry from "$lib/components/ui/QuietListEntry.svelte";');
    expect(pageSource).toContain('import TeacherLiveLauncher from "$lib/components/teacher-home/TeacherLiveLauncher.svelte";');
    expect(pageSource).toContain('title="Weiterarbeiten"');
    expect(pageSource).toContain("Unterrichten");
    expect(pageSource).toContain("Vorbereiten");
    expect(pageSource).not.toContain("Lehrenden-Welt");
    expect(pageSource).not.toContain("Arbeitsbereiche");
    expect(pageSource).not.toContain("Bereich öffnen");
  });
});
