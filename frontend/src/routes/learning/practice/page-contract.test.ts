import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

describe("practice page contract", () => {
  it("offers stack selection and safe session controls", () => {
    const source = readFileSync("src/routes/learning/practice/+page.svelte", "utf8");
    expect(source).toContain("Übungsstapel auswählen");
    expect(source).toContain("Fällige Aufgaben");
    expect(source).toContain("Aufgabe überspringen");
    expect(source).toContain("Sitzung beenden");
    expect(source).toContain("Antwort zur Auswertung senden");
    expect(source).toContain("Musterlösung anzeigen");
    expect(source).toContain("Die Rückmeldung wird vorbereitet");
    expect(source).not.toContain("teacher_context_md");
    expect(source).not.toContain("model_solution_md");
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
    expect(page).toContain("Die Auswertung ist technisch fehlgeschlagen");
    expect(sessionType).toContain("latest_attempt_id: string | null;");
  });
});
