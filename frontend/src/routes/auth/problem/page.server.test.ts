import { expect, it } from "vitest";
import { load } from "./+page.server";
it("offers an explicit retry when only local logout succeeded", () => {
  const data = load({ url: new URL("https://app.example/auth/problem?reason=local_logout_only") } as never);
  expect(data).toMatchObject({ actionHref: "/auth/logout", actionLabel: "Abmeldung erneut versuchen" });
});
it("never echoes private callback data into the error page", () => {
  const data = load({ url: new URL("https://app.example/auth/problem?reason=secret-value") } as never);
  expect(JSON.stringify(data)).not.toContain("secret-value");
});
