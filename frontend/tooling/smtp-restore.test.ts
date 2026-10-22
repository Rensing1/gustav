import { describe, expect, it } from "vitest";
import { restorableSmtp } from "../e2e/support/smtp-restore";

describe("temporary realm SMTP recovery", () => {
  const original = { host: "smtp.school.example", user: "mailer", password: "**********", port: "587" };
  it("records the actual configured credential instead of Keycloak's mask", () => {
    expect(restorableSmtp(original, { ...original, password: "test-password" }))
      .toEqual({ ...original, password: "test-password" });
    expect(original.password).toBe("**********");
  });
  it.each([
    { host: "smtp.school.example", user: "mailer" },
    { host: "other.example", user: "mailer", password: "test-password" },
    { host: "smtp.school.example", user: "other", password: "test-password" },
  ])("refuses to replace SMTP when the credential cannot be restored", configured => {
    expect(() => restorableSmtp(original, configured)).toThrow("Cannot safely restore");
  });
  it("preserves unmasked and anonymous SMTP configurations", () => {
    expect(restorableSmtp({ host: "local", password: "actual" }, {})).toEqual({ host: "local", password: "actual" });
    expect(restorableSmtp({ host: "local", auth: "false" }, {})).toEqual({ host: "local", auth: "false" });
  });
});
