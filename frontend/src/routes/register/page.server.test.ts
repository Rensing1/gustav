import { describe, expect, it, vi } from "vitest";

vi.mock("$env/dynamic/private", () => ({
  env: {
    ALLOWED_REGISTRATION_DOMAINS: "@school.example"
  }
}));

import { actions } from "./+page.server";

function requestWithForm(form: FormData) {
  return {
    formData: async () => form
  } as Parameters<typeof actions.default>[0]["request"];
}

describe("register page server action", () => {
  it("forwards a safe redirect target to the auth bridge", async () => {
    const form = new FormData();
    form.set("login_hint", "alice@school.example");
    form.set("redirect", "/teaching/courses/course-1");

    await expect(
      actions.default({
        request: requestWithForm(form),
        url: new URL("https://app.localhost/register?redirect=/learning")
      } as Parameters<typeof actions.default>[0])
    ).rejects.toMatchObject({
      status: 303,
      location: "/auth/register?login_hint=alice%40school.example&redirect=%2Fteaching%2Fcourses%2Fcourse-1"
    });
  });
});
