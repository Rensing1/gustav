import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  clearE2ESmtpRestore,
  registerE2EH5PContent,
  registerE2ESmtpRestore,
  registerE2EUser
} from "../e2e/support/e2e-run-state";


describe("feature acceptance run state", () => {
  it("records one exact run-owned identity without duplicates", () => {
    const directory = mkdtempSync(join(tmpdir(), "gustav-e2e-state-"));
    const statePath = join(directory, "state.json");
    const runId = "0123456789ab";
    writeFileSync(
      statePath,
      `${JSON.stringify({ version: 2, run_id: runId, users: [] })}\n`,
      { mode: 0o600 }
    );

    registerE2EUser(
      { email: `teacher.e2e-${runId}@example.com`, role: "teacher" },
      { statePath, runId }
    );
    registerE2EUser(
      { email: `teacher.e2e-${runId}@example.com`, role: "teacher" },
      { statePath, runId }
    );

    const state = JSON.parse(readFileSync(statePath, "utf8"));
    expect(state.users).toEqual([
      { email: `teacher.e2e-${runId}@example.com`, role: "teacher" }
    ]);
  });

  it("refuses an identity that is not owned by the active run", () => {
    const directory = mkdtempSync(join(tmpdir(), "gustav-e2e-state-"));
    const statePath = join(directory, "state.json");
    const runId = "0123456789ab";
    writeFileSync(
      statePath,
      `${JSON.stringify({ version: 2, run_id: runId, users: [] })}\n`,
      { mode: 0o600 }
    );

    expect(() =>
      registerE2EUser(
        { email: "real.teacher@example.com", role: "teacher" },
        { statePath, runId }
      )
    ).toThrow(/active E2E run/);
  });

  it("binds every exact H5P content id to its registered run-owned teacher", () => {
    const directory = mkdtempSync(join(tmpdir(), "gustav-e2e-state-"));
    const statePath = join(directory, "state.json");
    const runId = "0123456789ab";
    writeFileSync(
      statePath,
      `${JSON.stringify({
        version: 2,
        run_id: runId,
        users: [{ email: `teacher.e2e-${runId}@example.com`, role: "teacher" }],
        h5p_contents: []
      })}\n`,
      { mode: 0o600 }
    );

    const ownerEmail = `teacher.e2e-${runId}@example.com`;
    registerE2EH5PContent("271828", ownerEmail, { statePath, runId });
    expect(() => registerE2EH5PContent("../foreign", ownerEmail, { statePath, runId })).toThrow(
      /H5P content id/
    );
    expect(() =>
      registerE2EH5PContent("314159", `foreign.e2e-${runId}@example.com`, { statePath, runId })
    ).toThrow(/registered run-owned teacher/);
    expect(JSON.parse(readFileSync(statePath, "utf8")).h5p_contents).toEqual([
      { content_id: "271828", owner_email: ownerEmail }
    ]);
  });

  it("persists recoverable SMTP state until it is explicitly cleared", () => {
    const directory = mkdtempSync(join(tmpdir(), "gustav-e2e-state-"));
    const statePath = join(directory, "state.json");
    const runId = "0123456789ab";
    writeFileSync(
      statePath,
      `${JSON.stringify({ version: 2, run_id: runId, users: [], h5p_contents: [] })}\n`,
      { mode: 0o600 }
    );

    registerE2ESmtpRestore({ host: "smtp.local", port: "2525" }, { statePath, runId });
    expect(JSON.parse(readFileSync(statePath, "utf8"))).toMatchObject({
      keycloak_smtp_restore: { host: "smtp.local", port: "2525" }
    });

    clearE2ESmtpRestore({ statePath, runId });
    const state = JSON.parse(readFileSync(statePath, "utf8"));
    expect(state.keycloak_smtp_restore).toBeUndefined();
  });
});
