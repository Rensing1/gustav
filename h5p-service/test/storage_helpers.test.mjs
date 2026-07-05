import assert from "node:assert/strict";
import test from "node:test";

import {
  buildStorageDirs,
  probeStorageDirs,
  sanitizeHeaderFilename,
} from "../lib/storage_helpers.mjs";


test("buildStorageDirs returns the expected H5P storage layout", () => {
  assert.deepEqual(buildStorageDirs("/data/h5p"), {
    root: "/data/h5p",
    libraries: "/data/h5p/libraries",
    content: "/data/h5p/content",
    tmp: "/data/h5p/tmp",
    userdata: "/data/h5p/userdata",
    uploads: "/data/h5p/uploads",
  });
});


test("probeStorageDirs creates required directories and checks tmp write access", async () => {
  const created = [];
  const accessChecks = [];
  const dirs = buildStorageDirs("/data/h5p");

  const result = await probeStorageDirs(dirs, {
    mkdir: async (dir, options) => {
      created.push([dir, options]);
    },
    access: async (dir, mode) => {
      accessChecks.push([dir, mode]);
    },
    writeFlag: 2,
  });

  assert.deepEqual(result, { ok: true, root: "/data/h5p" });
  assert.deepEqual(created, [
    ["/data/h5p/libraries", { recursive: true }],
    ["/data/h5p/content", { recursive: true }],
    ["/data/h5p/tmp", { recursive: true }],
    ["/data/h5p/userdata", { recursive: true }],
    ["/data/h5p/uploads", { recursive: true }],
  ]);
  assert.deepEqual(accessChecks, [["/data/h5p/tmp", 2]]);
});


test("probeStorageDirs reports storage errors without throwing", async () => {
  const result = await probeStorageDirs(buildStorageDirs("/data/h5p"), {
    mkdir: async () => {
      throw new Error("disk is read-only");
    },
  });

  assert.equal(result.ok, false);
  assert.equal(result.root, "/data/h5p");
  assert.match(result.error, /disk is read-only/);
});


test("sanitizeHeaderFilename keeps Content-Disposition filenames conservative", () => {
  assert.equal(sanitizeHeaderFilename(" content/with spaces\r\n.zip "), "content_with_spaces_.zip");
  assert.equal(sanitizeHeaderFilename(""), "download");
  assert.equal(sanitizeHeaderFilename("!!!"), "_");
  assert.equal(sanitizeHeaderFilename("a".repeat(100)), "a".repeat(80));
});
