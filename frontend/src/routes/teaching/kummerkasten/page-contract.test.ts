import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("teacher concern box route contract", () => {
  it("uses shared page head, mode switch, quiet list, and inbox entry components", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const serverSource = readFileSync(path.resolve(currentDir, "+page.server.ts"), "utf8");

    expect(routeSource).toContain('import PageActionHead from "$lib/components/ui/PageActionHead.svelte";');
    expect(routeSource).toContain('import ModeSwitch from "$lib/components/ui/ModeSwitch.svelte";');
    expect(routeSource).toContain('import QuietList from "$lib/components/ui/QuietList.svelte";');
    expect(routeSource).toContain('import ConcernBoxInboxEntry from "$lib/components/concern-box/ConcernBoxInboxEntry.svelte";');
    expect(routeSource).toContain("<PageActionHead");
    expect(routeSource).toContain("<ModeSwitch");
    expect(routeSource).toContain("<QuietList");
    expect(routeSource).toContain("<ConcernBoxInboxEntry");
    expect(serverSource).toContain("hidePageHeading: true");
  });
});
