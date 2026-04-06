import { describe, expect, it } from "vitest";

import { __testables } from "./+page.server";

describe("teacher node editor server helpers", () => {
  it("parses repeated criteria fields into a bounded list", () => {
    const formData = new FormData();
    formData.set("task_kind", "native");
    formData.set("instruction_md", "Arbeite den Text durch.");

    for (let index = 0; index < 12; index += 1) {
      formData.append("criteria[]", `Kriterium ${index + 1}`);
    }
    formData.append("criteria[]", "   ");

    const parsed = __testables.taskPayloadFromForm(formData, {
      allowImplicitInstructionForH5P: true
    });

    expect(parsed.ok).toBe(true);
    if (!parsed.ok) {
      return;
    }
    expect(parsed.payload.criteria).toEqual([
      "Kriterium 1",
      "Kriterium 2",
      "Kriterium 3",
      "Kriterium 4",
      "Kriterium 5",
      "Kriterium 6",
      "Kriterium 7",
      "Kriterium 8",
      "Kriterium 9",
      "Kriterium 10"
    ]);
    expect(parsed.values.criteria_items).toHaveLength(10);
  });
});
