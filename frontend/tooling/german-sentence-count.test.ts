import { describe, expect, it } from "vitest";

import { countGermanSentences } from "../e2e/support/german-sentence-count";

describe("countGermanSentences", () => {
  it("treats a German abbreviation as part of one sentence", () => {
    expect(countGermanSentences("Sie nennen z. B. einen passenden Beleg.")).toBe(1);
  });

  it("counts separate sentences and ignores surrounding whitespace", () => {
    expect(countGermanSentences("  Sie erklären den Zusammenhang. Ergänzen Sie einen Beleg!  ")).toBe(2);
    expect(countGermanSentences("   ")).toBe(0);
  });
});
