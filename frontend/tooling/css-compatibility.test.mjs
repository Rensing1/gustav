import assert from "node:assert/strict";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import { assertNoCascadeLayers, findCascadeLayers } from "./css-compatibility.mjs";

test("finds named and anonymous cascade layers", () => {
  const css = `
    @layer reset, components;
    @layer components { .button { display: inline-flex; } }
    @LAYER { .notice { color: red; } }
  `;

  assert.deepEqual(findCascadeLayers(css), ["reset, components", "components", "<anonymous>"]);
});

test("finds named and anonymous cascade layers on imports", () => {
  const css = `
    @import url("./tokens.css") layer(tokens);
    @import "./defaults.css" /* valid CSS whitespace */ layer;
  `;

  assert.deepEqual(findCascadeLayers(css), ["tokens", "<anonymous import>"]);
});

test("accepts compatible at-rules and ignores layer text in comments", () => {
  const css = `
    /* @layer is documentation here. */
    @import url("./layer(theme).css") screen;
    @media (min-width: 40rem) { .workspace { display: grid; } }
    @supports (display: grid) { .workspace { gap: 1rem; } }
  `;

  assert.deepEqual(findCascadeLayers(css), []);
});

test("rejects cascade layers in nested generated CSS files", async (context) => {
  const directory = await mkdtemp(path.join(tmpdir(), "gustav-css-compatibility-"));
  context.after(() => rm(directory, { recursive: true, force: true }));
  await mkdir(path.join(directory, "nested"));
  await writeFile(path.join(directory, "nested", "app.css"), "@layer app { body { margin: 0; } }");

  await assert.rejects(
    assertNoCascadeLayers(directory),
    /nested\/app\.css: app/
  );
});

test("accepts a generated CSS directory without cascade layers", async (context) => {
  const directory = await mkdtemp(path.join(tmpdir(), "gustav-css-compatibility-"));
  context.after(() => rm(directory, { recursive: true, force: true }));
  await writeFile(path.join(directory, "app.css"), ".app-shell { min-height: 100vh; }");

  await assert.doesNotReject(assertNoCascadeLayers(directory));
});
