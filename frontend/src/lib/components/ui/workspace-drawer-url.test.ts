import { describe, expect, it } from "vitest";

import { withoutQueryParameters } from "./workspace-drawer-url";

describe("withoutQueryParameters", () => {
  it("removes drawer state while preserving unrelated query and hash state", () => {
    expect(
      withoutQueryParameters(
        "https://app.localhost/teaching/courses/course-1?course=1&view=compact#members",
        ["course"]
      )
    ).toBe("/teaching/courses/course-1?view=compact#members");
  });

  it("removes the complete member drawer query family", () => {
    expect(
      withoutQueryParameters(
        "/teaching/courses/course-1?members=1&add-member=1&member-q=anna&view=compact",
        ["members", "add-member", "member-q"]
      )
    ).toBe("/teaching/courses/course-1?view=compact");
  });
});
