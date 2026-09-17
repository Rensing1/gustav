import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { e2eDatabaseUrl } from "./e2e-env";

/** Control only the acceptance browser's own session; no runtime test endpoint. */
export function sessionFixture(action: "expire-access" | "refresh-reserved", cookie: string, subject: string): boolean {
  if (!e2eDatabaseUrl) throw new Error("The local acceptance database is required");
  const result = execFileSync("../.venv/bin/python", ["-c", `
import json, sys, psycopg
value = json.load(sys.stdin)
with psycopg.connect(value['dsn']) as conn:
    args = (value['hash'], value['subject'])
    if value['action'] == 'expire-access':
        result = conn.execute("update public.app_sessions set access_expires_at=now()-interval '1 second' where session_id=%s and sub=%s", args).rowcount == 1
    else:
        row = conn.execute("select refresh_locked_until is not null from public.app_sessions where session_id=%s and sub=%s", args).fetchone()
        result = bool(row and row[0])
print('yes' if result else 'no')
`], { input: JSON.stringify({ dsn: e2eDatabaseUrl, hash: createHash("sha256").update(cookie).digest("hex"), subject, action }), timeout: 5_000 });
  return result.toString().trim() === "yes";
}
