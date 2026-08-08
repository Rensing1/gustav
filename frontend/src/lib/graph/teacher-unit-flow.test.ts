import { describe, expect, it } from "vitest";

import { formatGraphCounts } from "./teacher-unit-flow";

describe("teacher unit graph copy", () => {
  it("uses correct German singular and plural forms", () => {
    expect(formatGraphCounts(0, 0)).toBe("0 Materialien · 0 Aufgaben");
    expect(formatGraphCounts(1, 1)).toBe("1 Material · 1 Aufgabe");
    expect(formatGraphCounts(2, 3)).toBe("2 Materialien · 3 Aufgaben");
  });
});
