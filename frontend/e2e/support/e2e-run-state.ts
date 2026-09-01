import { chmodSync, readFileSync, renameSync, writeFileSync } from "node:fs";


type E2ERole = "teacher" | "student";

type E2EUser = {
  email: string;
  role: E2ERole;
  keycloak_id?: string;
};

type E2EH5PContent = {
  content_id: string;
  owner_email: string;
};

type E2EState = {
  version: 2;
  run_id: string;
  users: E2EUser[];
  h5p_contents?: E2EH5PContent[];
  keycloak_smtp_restore?: Record<string, string>;
  worker_pause_requested?: boolean;
};

type RegistrationOptions = {
  statePath?: string;
  runId?: string;
};

function runState(options: RegistrationOptions): {
  statePath: string;
  runId: string;
  state: E2EState;
} | null {
  const statePath = options.statePath ?? process.env.E2E_STATE_PATH ?? "";
  const runId = options.runId ?? process.env.E2E_RUN_ID ?? "";
  if (!statePath && !runId) return null;
  if (!statePath || !/^[0-9a-f]{12}$/.test(runId)) {
    throw new Error("Feature acceptance run state is incomplete");
  }
  const state = JSON.parse(readFileSync(statePath, "utf8")) as E2EState;
  if (state.version !== 2 || state.run_id !== runId || !Array.isArray(state.users)) {
    throw new Error("Feature acceptance run state is invalid");
  }
  return { statePath, runId, state };
}

function writeRunState(statePath: string, state: E2EState): void {
  const temporary = `${statePath}.${process.pid}.tmp`;
  writeFileSync(temporary, `${JSON.stringify(state)}\n`, { mode: 0o600 });
  chmodSync(temporary, 0o600);
  renameSync(temporary, statePath);
  chmodSync(statePath, 0o600);
}

/** Record an exact synthetic identity before Keycloak creates it. */
export function registerE2EUser(user: E2EUser, options: RegistrationOptions = {}): void {
  const active = runState(options);
  if (!active) return;
  if (!user.email.toLowerCase().includes(`.e2e-${active.runId}@`)) {
    throw new Error("Identity does not belong to the active E2E run");
  }
  if (user.keycloak_id && !/^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(user.keycloak_id)) {
    throw new Error("Invalid Keycloak id for the active E2E run");
  }

  const existing = active.state.users.find((candidate) => candidate.email === user.email);
  if (existing) {
    if (existing.role !== user.role) throw new Error("E2E identity role changed within one run");
    if (user.keycloak_id) existing.keycloak_id = user.keycloak_id;
  } else {
    active.state.users.push(user);
  }
  writeRunState(active.statePath, active.state);
}

/** Bind one exact H5P id to the registered teacher who created it. */
export function registerE2EH5PContent(
  contentId: string,
  ownerEmail: string,
  options: RegistrationOptions = {}
): void {
  const active = runState(options);
  if (!active) return;
  if (!/^[1-9][0-9]*$/.test(contentId)) {
    throw new Error("Invalid H5P content id for the active E2E run");
  }
  const normalizedOwner = ownerEmail.toLowerCase();
  const owner = active.state.users.find(
    (user) => user.role === "teacher" && user.email.toLowerCase() === normalizedOwner
  );
  if (!owner || !normalizedOwner.includes(`.e2e-${active.runId}@`)) {
    throw new Error("H5P content owner must be a registered run-owned teacher");
  }
  const contents = Array.isArray(active.state.h5p_contents) ? active.state.h5p_contents : [];
  if (!contents.some((content) => content.content_id === contentId)) {
    contents.push({ content_id: contentId, owner_email: owner.email });
  }
  active.state.h5p_contents = contents;
  writeRunState(active.statePath, active.state);
}

/** Save the exact prior SMTP configuration before the temporary update. */
export function registerE2ESmtpRestore(
  smtpServer: Record<string, string>,
  options: RegistrationOptions = {}
): void {
  const active = runState(options);
  if (!active) return;
  if (Object.entries(smtpServer).some(([key, value]) => !key || typeof value !== "string")) {
    throw new Error("Invalid SMTP recovery state");
  }
  active.state.keycloak_smtp_restore = { ...smtpServer };
  writeRunState(active.statePath, active.state);
}

/** Clear SMTP recovery only after Keycloak accepted the restoration. */
export function clearE2ESmtpRestore(options: RegistrationOptions = {}): void {
  const active = runState(options);
  if (!active) return;
  delete active.state.keycloak_smtp_restore;
  writeRunState(active.statePath, active.state);
}
