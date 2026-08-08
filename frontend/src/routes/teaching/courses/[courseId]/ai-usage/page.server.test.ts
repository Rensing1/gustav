import { describe, expect, it } from "vitest";

import { buildUsageApiSearch } from "./usage-search";

describe("teacher course AI usage page server", () => {
  it("maps inclusive Berlin calendar days to the API's exclusive upper boundary", () => {
    const search = buildUsageApiSearch(
      new URLSearchParams({ from_date: "2026-03-29", to_date: "2026-03-29", unit_id: "unit-1" })
    );

    expect(search.get("from")).toBe("2026-03-29");
    expect(search.get("to")).toBe("2026-03-30");
    expect(search.get("unit_id")).toBe("unit-1");
  });

  it("keeps the unfiltered view free of artificial time boundaries", () => {
    expect(buildUsageApiSearch(new URLSearchParams()).toString()).toBe("");
  });
});
