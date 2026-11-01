import { describe, expect, it, vi } from "vitest";

import { createTiptapMarkdownEditor } from "./tiptap-markdown-editor";

describe("Tiptap Markdown adapter", () => {
  it("preserves inline code and inert code blocks through save and reload", () => {
    const host = document.createElement("div");
    const content = 'Dateien: `.sb3`, `.hex` und `.fls`.\n\n```js\nwindow.__executed = true;\n<script>alert(1)</script>\n```';
    const options = { element: host, content, placeholder: "Material", onUpdate: vi.fn() };
    const editor = createTiptapMarkdownEditor(options);
    const saved = editor.getMarkdown();
    editor.destroy();
    const reopened = createTiptapMarkdownEditor({ ...options, content: saved });
    expect(reopened.getMarkdown()).toBe(content);
    expect(host.querySelectorAll("code")).toHaveLength(4);
    expect(host.querySelector("script")).toBeNull();
    reopened.destroy();
  });
  it("round-trips the supported Markdown without changing the storage contract", () => {
    const onUpdate = vi.fn();
    const editor = createTiptapMarkdownEditor({
      element: document.createElement("div"),
      content: "# Überschrift\n\n**fett** und *kursiv*\n\n- eins\n- zwei",
      placeholder: "Material",
      onUpdate
    });

    expect(editor.getMarkdown()).toContain("# Überschrift");
    expect(editor.getMarkdown()).toContain("**fett**");
    expect(editor.getMarkdown()).toContain("*kursiv*");
    expect(editor.getMarkdown()).toContain("- eins");
    editor.destroy();
  });

  it("creates and edits a visual table as Markdown", () => {
    const editor = createTiptapMarkdownEditor({
      element: document.createElement("div"),
      content: "",
      placeholder: "Material",
      onUpdate: vi.fn()
    });

    editor.insertTable();
    const initialTable = editor.getMarkdown();
    expect(initialTable).toContain("| --- |");

    editor.addRowAfter();
    expect(editor.getMarkdown().split("\n").length).toBeGreaterThan(initialTable.split("\n").length);
    editor.destroy();
  });

  it("does not enable embedded image nodes", () => {
    const editor = createTiptapMarkdownEditor({
      element: document.createElement("div"),
      content: "plain text",
      placeholder: "Material",
      onUpdate: vi.fn()
    });

    expect(editor.hasNode("image")).toBe(false);
    editor.destroy();
  });

  it("can switch the editing surface between locked and editable", () => {
    const host = document.createElement("div");
    const editor = createTiptapMarkdownEditor({
      element: host,
      content: "Entwurf",
      placeholder: "Material",
      editable: false,
      onUpdate: vi.fn()
    });

    expect(host.querySelector('[contenteditable="false"]')).not.toBeNull();
    editor.setEditable(true);
    expect(host.querySelector('[contenteditable="true"]')).not.toBeNull();
    editor.destroy();
  });
});


it("preserves Mermaid language, indentation and HTML labels after an edit and reopen", () => {
  const source = "sequenceDiagram\n    participant A as <Alice>\n\n    A->>B: Grüße\n\tB-->>A: Hallo";
  const host = document.createElement("div");
  const options = { element: host, content: "```mermaid\n" + source + "\n```", placeholder: "Material", onUpdate: vi.fn() };
  const editor = createTiptapMarkdownEditor(options);
  editor.setMarkdown(options.content.replace("Hallo", "Antwort"));
  const saved = editor.getMarkdown();
  editor.destroy();
  const reopened = createTiptapMarkdownEditor({ ...options, content: saved });
  expect(host.querySelector("pre code")?.textContent).toBe(source.replace("Hallo", "Antwort"));
  expect(reopened.getMarkdown()).toContain("```mermaid");
  reopened.destroy();
});
