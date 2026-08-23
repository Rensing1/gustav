import { describe, expect, it } from "vitest";

import { criterionLevel, normalizedCriterionScore } from "./criterion-level";

describe("criterion-level", () => {
  it.each([
    [0, "Mangelhaft"],
    [2, "Mangelhaft"],
    [3, "Ansatzweise"],
    [6, "Ansatzweise"],
    [7, "Gelungen"],
    [8, "Gelungen"],
    [9, "Hervorragend"],
    [10, "Hervorragend"]
  ] as const)("maps %s/10 to %s", (score, expected) => {
    expect(criterionLevel(score, 10)).toBe(expected);
  });

  it("normalizes other maxima without rounding", () => {
    expect(normalizedCriterionScore(1, 4)).toBe(2.5);
    expect(criterionLevel(1, 4)).toBe("Ansatzweise");
    expect(criterionLevel(3, 4)).toBe("Gelungen");
    expect(criterionLevel(9, null)).toBe("Hervorragend");
  });

  it.each([
    [null, 10],
    [undefined, 10],
    [-1, 10],
    [11, 10],
    [1, 0],
    [1, -1]
  ])("returns no level value for invalid score %s and maximum %s", (score, maximum) => {
    expect(normalizedCriterionScore(score, maximum)).toBeNull();
    expect(criterionLevel(score, maximum)).toBe("Ohne Einstufung");
  });
});
