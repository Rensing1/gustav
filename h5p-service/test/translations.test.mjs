import assert from "node:assert/strict";
import test from "node:test";
import { translateH5p } from "../lib/translations.mjs";

test("uses bundled German metadata and preserves the library fallback contract", () => {
  assert.equal(translateH5p("metadata-semantics:title", "de"), "Titel");
  assert.equal(translateH5p("metadata-semantics:title", "en"), "Title");
  assert.equal(translateH5p("unknown:author-text", "de"), "unknown:author-text");
  assert.equal(translateH5p("metadata-semantics:title", "../../secrets"), "Titel");
});
