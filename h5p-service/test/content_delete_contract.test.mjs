import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";


test("server exposes a teacher-only delete endpoint for H5P contents", () => {
  const source = readFileSync(path.resolve("server.mjs"), "utf8");

  assert.match(source, /app\.delete\("\/contents\/:contentId",\s*requireTeacher/);
  assert.match(source, /await h5pEditor\.deleteContent\(contentId,\s*req\.user\)/);
});
