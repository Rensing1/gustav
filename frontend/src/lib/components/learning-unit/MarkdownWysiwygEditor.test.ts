import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const editorSourcePath = path.resolve(currentDir, "MarkdownWysiwygEditor.svelte");
const appCssPath = path.resolve(currentDir, "../../styles/app.css");

describe("MarkdownWysiwygEditor", () => {
  it("initializes Toast UI with pixel heights because the editor parses height values numerically", () => {
    const source = readFileSync(editorSourcePath, "utf8");

    expect(source).toMatch(/height:\s*"448px"/);
    expect(source).toMatch(/minHeight:\s*"352px"/);
    expect(source).toContain("Toast UI parses these values as pixel numbers internally");
    expect(source).not.toMatch(/height:\s*"28rem"/);
    expect(source).not.toMatch(/minHeight:\s*"22rem"/);
  });

  it("keeps Toast UI's main editor area shrinkable and enables touch scrolling inside ProseMirror", () => {
    const css = readFileSync(appCssPath, "utf8");
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
