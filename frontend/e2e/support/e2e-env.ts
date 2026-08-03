import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

export function loadLocalEnvDefaults(): void {
  const envPathCandidates = [path.resolve(process.cwd(), ".env"), path.resolve(process.cwd(), "..", ".env")];
  const envPath = envPathCandidates.find((candidate) => existsSync(candidate));
  if (!envPath) {
    return;
  }

  const lines = readFileSync(envPath, "utf8").split(/\r?\n/);
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) {
      continue;
    }
    const [rawKey, ...rawValueParts] = trimmed.split("=");
    const key = rawKey.trim();
    if (process.env[key]) {
      continue;
    }
    const rawValue = rawValueParts.join("=").trim();
    process.env[key] = rawValue.replace(/^['"]|['"]$/g, "");
  }
}

loadLocalEnvDefaults();

export const webBase = (process.env.WEB_BASE ?? "https://app.localhost").replace(/\/$/, "");
export const kcBase = (process.env.KC_BASE ?? "https://id.localhost").replace(/\/$/, "");
export const realm = process.env.KC_REALM ?? "gustav";
export const adminRealm = process.env.KC_ADMIN_REALM ?? "master";
export const adminClientId = process.env.KC_ADMIN_CLIENT_ID ?? "gustav-admin-cli";
export const adminClientSecret = (process.env.KC_ADMIN_CLIENT_SECRET ?? "").trim();
export const adminUser = process.env.KEYCLOAK_ADMIN ?? "admin";
export const adminPassword = process.env.KEYCLOAK_ADMIN_PASSWORD ?? "admin";
export const e2eDatabaseUrl = hostAccessibleDatabaseUrl(
  (process.env.E2E_DATABASE_URL ?? process.env.SESSION_DATABASE_URL ?? "").trim()
);
export const emailDomain = deriveEmailDomain();

function hostAccessibleDatabaseUrl(value: string): string {
  if (!value) return "";
  const parsed = new URL(value);
  if (parsed.hostname.startsWith("supabase_db_")) {
    parsed.hostname = "127.0.0.1";
    parsed.port = process.env.SUPABASE_DB_PORT?.trim() || "54322";
  }
  return parsed.toString();
}

function deriveEmailDomain(): string {
  const explicit = process.env.E2E_EMAIL_DOMAIN?.trim();
  if (explicit) {
    return explicit.replace(/^@/, "");
  }

  const allowed = process.env.ALLOWED_REGISTRATION_DOMAINS?.split(",")
    .map((entry) => entry.trim().replace(/^@/, ""))
    .find(Boolean);
  return allowed ?? "example.com";
}
