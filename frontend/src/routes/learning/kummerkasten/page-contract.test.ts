import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("learner concern box route contract", () => {
  it("uses a shared page head and shared composer component", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const serverSource = readFileSync(path.resolve(currentDir, "+page.server.ts"), "utf8");

    expect(routeSource).toContain('import PageActionHead from "$lib/components/ui/PageActionHead.svelte";');
    expect(routeSource).toContain('import ConcernBoxComposer from "$lib/components/concern-box/ConcernBoxComposer.svelte";');
    expect(routeSource).toContain("<PageActionHead");
    expect(routeSource).toContain("<ConcernBoxComposer");
    expect(serverSource).toContain("hidePageHeading: true");
  });
});
