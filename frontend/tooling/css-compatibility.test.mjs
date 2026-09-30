import assert from "node:assert/strict";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import { assertBrowserCompatibleCss, findCascadeLayers, findMissingBrowserFallbacks } from "./css-compatibility.mjs";

test("requires viewport and graph stroke fallbacks and gated dialog custom properties", () => {
  assert.deepEqual(findMissingBrowserFallbacks(".graph { height: 100dvh; stroke: color-mix(in srgb, black, white); --dialog-border-soft: color-mix(in srgb, black, white); }"), ["height", "stroke", "--dialog-border-soft"]);
  assert.deepEqual(findMissingBrowserFallbacks(".graph { height: 100vh; height: 100dvh; stroke: black; stroke: color-mix(in srgb, black, white); --dialog-border-soft: black; } @supports (color: color-mix(in srgb, black, white)) { .graph { --dialog-border-soft: color-mix(in srgb, black, white); } }"), []);
});

test("a preceding value cannot rescue deferred parsing of unsupported values with var()", () => {
  assert.deepEqual(findMissingBrowserFallbacks(".graph { stroke: black; stroke: color-mix(in srgb, var(--color-border), white); height: 100vh; height: calc(100dvh - var(--space-4)); }"), ["stroke", "height"]);
  assert.deepEqual(findMissingBrowserFallbacks(".graph { stroke: black; height: 100vh; } @supports (color: color-mix(in srgb, black, white)) { .graph { stroke: color-mix(in srgb, var(--color-border), white); } } @supports (height: 100dvh) { .graph { height: calc(100dvh - var(--space-4)); } }"), []);
  assert.deepEqual(findMissingBrowserFallbacks("@supports not (color: color-mix(in srgb, black, white)) { .graph { stroke: color-mix(in srgb, var(--color-border), white); } }"), ["stroke"]);
});

test("shipped graph and workspace styles satisfy the selected fallback contracts", async () => {
  for (const file of ["learning-unit.css", "teaching-workspace.css", "practice.css", "app.css", "ui-primitives.css"]) {
    const css = await import("node:fs/promises").then(({ readFile }) => readFile(new URL(`../src/lib/styles/${file}`, import.meta.url), "utf8"));
    assert.deepEqual(findMissingBrowserFallbacks(css, file), [], file);
  }
});

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
    @import "./commented.css"/**/layer(commented);
    @import url("./screen.css")/**/layer(screen)screen;
  `;

  assert.deepEqual(findCascadeLayers(css), [
    "tokens",
    "<anonymous import>",
    "commented",
    "screen"
  ]);
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
    assertBrowserCompatibleCss(directory),
    /nested\/app\.css: app/
  );
});

test("accepts a generated CSS directory without cascade layers", async (context) => {
  const directory = await mkdtemp(path.join(tmpdir(), "gustav-css-compatibility-"));
  context.after(() => rm(directory, { recursive: true, force: true }));
  await writeFile(path.join(directory, "app.css"), ".app-shell { min-height: 100vh; }");

  await assert.doesNotReject(assertBrowserCompatibleCss(directory));
});
