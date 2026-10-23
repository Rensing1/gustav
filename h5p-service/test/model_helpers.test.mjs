import assert from "node:assert/strict";
import test from "node:test";

import {
  H5P_THEME_STYLESHEET_PATH,
  H5P_TOKEN_STYLESHEET_PATH,
  ensureDivEmbedTypes,
  ensureThemeStylesLast,
  ensureStateTransportLast,
} from "../lib/model_helpers.mjs";

test("player models load the state transport once after the H5P core", () => {
  const path = "/h5p/webcomponents/state-transport.js";
  assert.deepEqual(ensureStateTransportLast([path, "/h5p/core/js/h5p.js", path]), ["/h5p/core/js/h5p.js", path]);
  assert.deepEqual(ensureStateTransportLast(undefined), [path]);
});


test("ensureThemeStylesLast appends the Gustav theme when styles are missing", () => {
  assert.deepEqual(ensureThemeStylesLast(undefined), [H5P_TOKEN_STYLESHEET_PATH, H5P_THEME_STYLESHEET_PATH]);
  assert.deepEqual(ensureThemeStylesLast("not-an-array"), [H5P_TOKEN_STYLESHEET_PATH, H5P_THEME_STYLESHEET_PATH]);
});


test("ensureThemeStylesLast keeps the theme stylesheet exactly once at the end", () => {
  const styles = [
    "/h5p/theme/h5p-gustav.css",
    "/libraries/core.css",
    "/content/local.css",
    H5P_TOKEN_STYLESHEET_PATH,
    "/h5p/theme/h5p-gustav.css",
  ];

  assert.deepEqual(ensureThemeStylesLast(styles), [
    "/libraries/core.css",
    "/content/local.css",
    H5P_TOKEN_STYLESHEET_PATH,
    H5P_THEME_STYLESHEET_PATH,
  ]);
});


test("ensureDivEmbedTypes advertises div first while preserving unique embed types", () => {
  assert.deepEqual(ensureDivEmbedTypes(undefined), ["div"]);
  assert.deepEqual(ensureDivEmbedTypes(["iframe", "div", "", "external", "iframe"]), [
    "div",
    "iframe",
    "external",
  ]);
});
