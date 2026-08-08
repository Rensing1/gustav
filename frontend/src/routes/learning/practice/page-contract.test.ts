import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

describe("practice page contract", () => {
  it("offers stack selection and safe session controls", () => {
    const source = readFileSync("src/routes/learning/practice/+page.svelte", "utf8");
    expect(source).toContain("Übungsstapel auswählen");
    expect(source).toContain("Fällige Aufgaben");
    expect(source).toContain("Aufgabe überspringen");
    expect(source).toContain("Sitzung beenden");
    expect(source).not.toContain("teacher_context_md");
    expect(source).not.toContain("model_solution_md");
  });
});
