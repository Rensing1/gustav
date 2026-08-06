import { execFile } from "node:child_process";
import { promisify } from "node:util";

import { e2eDatabaseUrl } from "./e2e-env";

const execFileAsync = promisify(execFile);
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/**
 * Reproduce a legacy course that predates mandatory metadata.
 *
 * New courses cannot enter this state through the public API. The fixture is
 * therefore limited to the production-like test database and never creates a
 * separate application code path.
 */
export async function makeCourseMetadataIncomplete(courseId: string): Promise<void> {
  if (!e2eDatabaseUrl) {
    throw new Error("E2E_DATABASE_URL or SESSION_DATABASE_URL is required for the legacy course fixture");
  }
  if (!uuidPattern.test(courseId)) {
    throw new Error("Invalid course id for legacy course fixture");
  }

  await execFileAsync(
    "psql",
    [
      e2eDatabaseUrl,
      "-X",
      "-v",
      "ON_ERROR_STOP=1",
      "-c",
      `update public.courses set subject = null, grade_level = null, school_year_start = null where id = '${courseId}'::uuid;`
    ],
    { encoding: "utf8", maxBuffer: 1024 * 1024 }
  );
}
