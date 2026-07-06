import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { readWorkspaceCssBundle } from "$lib/styles/test-css-bundle";

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const editorSourcePath = path.resolve(currentDir, "MarkdownWysiwygEditor.svelte");
const stylesDir = path.resolve(currentDir, "../../styles");

describe("MarkdownWysiwygEditor", () => {
  it("exposes table editing but keeps image upload out of the learner toolbar", () => {
    const source = readFileSync(editorSourcePath, "utf8");

    expect(source).toContain('"table"');
    expect(source).not.toContain('"image"');
  });

  it("renders a textarea fallback for failed editor initialization and no-JS form submission", () => {
    const source = readFileSync(editorSourcePath, "utf8");

    expect(source).toContain("<textarea");
    expect(source).toContain("{name}");
    expect(source).toContain("editorReady");
  });

  it("initializes the no-JS fallback value before client effects run", () => {
    const source = readFileSync(editorSourcePath, "utf8");

    expect(source).toContain("let fallbackValue = $derived");
    expect(source).toContain('String(value || "")');
    expect(source).toContain("value={fallbackValue}");
  });

  it("synchronizes the Toast UI markdown into the form immediately before submission", () => {
    const source = readFileSync(editorSourcePath, "utf8");

    expect(source).toContain('addEventListener("submit"');
    expect(source).toContain('addEventListener("formdata"');
    expect(source).toContain("syncEditorValue");
    expect(source).toContain("const nextValue = syncEditorValue();");
    expect(source).toContain("formData?.set(name, nextValue);");
  });

  it("initializes Toast UI with pixel heights because the editor parses height values numerically", () => {
    const source = readFileSync(editorSourcePath, "utf8");

    expect(source).toMatch(/height:\s*"448px"/);
    expect(source).toMatch(/minHeight:\s*"352px"/);
    expect(source).toContain("Toast UI parses these values as pixel numbers internally");
    expect(source).not.toMatch(/height:\s*"28rem"/);
    expect(source).not.toMatch(/minHeight:\s*"22rem"/);
  });

  it("keeps Toast UI's main editor area shrinkable and enables touch scrolling inside ProseMirror", () => {
    const css = readWorkspaceCssBundle(stylesDir);
    const mainRule = css.match(/\.learning-markdown-editor\s+\.toastui-editor-main\s*\{(?<body>[^}]*)\}/s);

    expect(mainRule?.groups?.body).toMatch(/min-height:\s*0(?:px)?\s*;/);
    expect(mainRule?.groups?.body).not.toMatch(/min-height:\s*40rem\s*;/);

    const proseMirrorRules = Array.from(
      css.matchAll(/\.learning-markdown-editor[^{}]*\.ProseMirror[^{}]*\{(?<body>[^}]*)\}/gs)
    )
      .map((match) => match.groups?.body ?? "")
      .join("\n");

    expect(proseMirrorRules).toMatch(/overflow-y:\s*auto\s*;/);
    expect(proseMirrorRules).toMatch(/-webkit-overflow-scrolling:\s*touch\s*;/);
  });
});
