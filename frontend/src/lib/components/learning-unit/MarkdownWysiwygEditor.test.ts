import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { readWorkspaceCssBundle } from "$lib/styles/test-css-bundle";

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const editorSourcePath = path.resolve(currentDir, "MarkdownWysiwygEditor.svelte");
const stylesDir = path.resolve(currentDir, "../../styles");

describe("MarkdownWysiwygEditor", () => {
  it("loads the maintained Tiptap adapter lazily and removes Toast UI", () => {
    const source = readFileSync(editorSourcePath, "utf8");

    expect(source).toContain('import("./tiptap-markdown-editor")');
    expect(source).not.toContain("@toast-ui/editor");
  });

  it("exposes visual table editing but keeps image and code controls out of the toolbar", () => {
    const source = readFileSync(editorSourcePath, "utf8");

    for (const action of ["insertTable", "addRowAfter", "deleteRow", "addColumnAfter", "deleteColumn", "deleteTable"]) {
      expect(source).toContain(action);
    }
    expect(source).not.toMatch(/image|codeBlock/);
  });

  it("renders a textarea fallback for failed editor initialization and no-JS form submission", () => {
    const source = readFileSync(editorSourcePath, "utf8");

    expect(source).toContain("<textarea");
    expect(source).toContain("{name}");
    expect(source).toContain("editorReady");
  });

  it("gives the accessible field name only to the currently interactive editor", () => {
    const source = readFileSync(editorSourcePath, "utf8");

    expect(source).toContain("aria-label={editorReady ? undefined : ariaLabel}");
  });

  it("initializes the no-JS fallback value before client effects run", () => {
    const source = readFileSync(editorSourcePath, "utf8");

    expect(source).toContain("let fallbackValue = $derived");
    expect(source).toContain('String(value || "")');
    expect(source).toContain("value={fallbackValue}");
  });

  it("synchronizes Tiptap markdown into the form immediately before submission", () => {
    const source = readFileSync(editorSourcePath, "utf8");

    expect(source).toContain('addEventListener("submit"');
    expect(source).toContain('addEventListener("formdata"');
    expect(source).toContain("syncEditorValue");
    expect(source).toContain("const nextValue = syncEditorValue();");
    expect(source).toContain("formData?.set(name, nextValue);");
  });

  it("propagates a disabled state to Tiptap, toolbar controls and the textarea fallback", () => {
    const source = readFileSync(editorSourcePath, "utf8");

    expect(source).toContain("disabled?: boolean");
    expect(source).toContain("activeEditor.setEditable(!nextDisabled)");
    expect(source).toMatch(/<fieldset[^>]*disabled=\{disabled\}/s);
    expect(source).toMatch(/<textarea[\s\S]*\{disabled\}/s);
  });

  it("keeps the Tiptap surface scrollable on touch devices", () => {
    const css = readWorkspaceCssBundle(stylesDir);
    const proseMirrorRules = Array.from(
      css.matchAll(/\.learning-markdown-editor[^{}]*\.tiptap[^{}]*\{(?<body>[^}]*)\}/gs)
    )
      .map((match) => match.groups?.body ?? "")
      .join("\n");

    expect(proseMirrorRules).toMatch(/overflow-y:\s*auto\s*;/);
    expect(proseMirrorRules).toMatch(/-webkit-overflow-scrolling:\s*touch\s*;/);
    expect(proseMirrorRules).toMatch(/min-height:\s*22rem\s*;/);
  });

  it("uses theme surfaces for one cohesive editor instead of fixed light colors", () => {
    const css = readWorkspaceCssBundle(stylesDir);
    const editorRules = Array.from(css.matchAll(/\.learning-markdown-editor[^{}]*\{(?<body>[^}]*)\}/gs))
      .map((match) => match.groups?.body ?? "")
      .join("\n");

    expect(editorRules).not.toMatch(/#fbf9f4|#f7f4ed|,\s*white\b/i);
    expect(editorRules).toContain("var(--color-bg-surface)");
    expect(editorRules).toContain("var(--color-bg-muted)");
    expect(editorRules).toContain("box-shadow: none");
    expect(css).toMatch(/\.learning-markdown-editor:focus-within\s*\{/);
    expect(css).toMatch(/\.learning-markdown-editor__toolbar button\.active\s*\{[^}]*border-bottom-color:\s*var\(--color-accent\)/s);
  });
});
