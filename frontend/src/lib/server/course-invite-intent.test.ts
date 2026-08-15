import { describe, expect, it } from "vitest";

import {
  parseCourseInviteIntent,
  serializeCourseInviteIntent
} from "./course-invite-intent";

const secret = "test-frontend-session-secret-with-32-bytes";

describe("course invitation intent cookie", () => {
  it("round-trips a signed, unaccepted intent", () => {
    const cookie = serializeCourseInviteIntent(
      { token: "v1.signed-capability-token", accepted: false, expiresAt: 2_000_000_000 },
      secret
    );
    expect(parseCourseInviteIntent(cookie, secret, 1_900_000_000)).toEqual({
      token: "v1.signed-capability-token",
      accepted: false,
      expiresAt: 2_000_000_000
    });
  });

  it("rejects tampering and expiry", () => {
    const cookie = serializeCourseInviteIntent(
      { token: "v1.signed-capability-token", accepted: true, expiresAt: 2_000_000_000 },
      secret
    );
    expect(parseCourseInviteIntent(`${cookie}x`, secret, 1_900_000_000)).toBeNull();
    expect(parseCourseInviteIntent(cookie, secret, 2_000_000_001)).toBeNull();
  });
});
