import { describe, expect, it } from "vitest";

import { taskInstructionPreview } from "./task-preview";

describe("task instruction preview", () => {
  it("keeps a short one-line instruction complete without a truncation hint", () => {
    expect(taskInstructionPreview("Nenne zwei Beispiele.", "Aufgabe 1")).toEqual({
      text: "Nenne zwei Beispiele.",
      truncated: false
    });
  });

  it("combines markdown sections and marks additional instructions", () => {
    const preview = taskInstructionPreview(
      "## Arbeitsauftrag\n\n**Erkläre** den Zusammenhang.\n\n- Nutze zwei Belege.\n- Begründe dein Ergebnis.",
      "Aufgabe 1"
    );

    expect(preview.text).toBe("Arbeitsauftrag Erkläre den Zusammenhang. Nutze zwei Belege. Begründe dein Ergebnis.");
    expect(preview.truncated).toBe(true);
  });

  it("falls back to the task title for an empty instruction", () => {
    expect(taskInstructionPreview(" \n\n ", "Aufgabe 8")).toEqual({ text: "Aufgabe 8", truncated: false });
  });
});
