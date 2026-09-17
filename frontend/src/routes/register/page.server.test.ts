import { expect, it } from "vitest";
import { load } from "./+page.server";
it("opens registration directly and preserves the invitation target", () => {
  expect(() => load({ url: new URL("https://app.example/register?redirect=%2Fcourse-invitations%2Finvite") } as never)).toThrow(expect.objectContaining({ status: 303, location: "/auth/register?redirect=%2Fcourse-invitations%2Finvite" }));
});
