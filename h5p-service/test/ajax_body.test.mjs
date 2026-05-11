import assert from "node:assert/strict";
import test from "node:test";

import { normalizeH5PAjaxBody } from "../lib/ajax_body.mjs";


test("normalizeH5PAjaxBody maps H5P urlencoded libraries[] arrays to libraries", () => {
  const body = {
    "libraries[]": ["H5P.AdvancedText 1.1", "H5P.Image 1.1"],
  };

  assert.deepEqual(normalizeH5PAjaxBody(body), {
    "libraries[]": ["H5P.AdvancedText 1.1", "H5P.Image 1.1"],
    libraries: ["H5P.AdvancedText 1.1", "H5P.Image 1.1"],
  });
});


test("normalizeH5PAjaxBody preserves existing libraries values", () => {
  const body = {
    "libraries[]": ["H5P.Image 1.1"],
    libraries: ["H5P.AdvancedText 1.1"],
  };

  assert.deepEqual(normalizeH5PAjaxBody(body), body);
});


test("normalizeH5PAjaxBody maps a single H5P urlencoded libraries[] value to an array", () => {
  const body = {
    "libraries[]": "H5P.Image 1.1",
  };

  assert.deepEqual(normalizeH5PAjaxBody(body), {
    "libraries[]": "H5P.Image 1.1",
    libraries: ["H5P.Image 1.1"],
  });
});
