import { describe, expect, it } from "vitest";

import { splitCourseInviteRecipients } from "./course-invite-recipients";

describe("course invitation recipient transport", () => {
  it("turns the teacher text field into the API array contract", () => {
    expect(splitCourseInviteRecipients(
      "first@school.example; second@school.example,\n third@school.example"
    )).toEqual([
      "first@school.example",
      "second@school.example",
      "third@school.example"
    ]);
  });

  it("drops empty separators but leaves validation and deduplication to the backend", () => {
    expect(splitCourseInviteRecipients(
      " Student@School.Example ;; student@school.example "
    )).toEqual(["Student@School.Example", "student@school.example"]);
  });
});
