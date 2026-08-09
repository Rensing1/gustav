import { describe, expect, it, vi } from "vitest";

import { createTiptapMarkdownEditor } from "./tiptap-markdown-editor";

describe("Tiptap Markdown adapter", () => {
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

  it("does not enable image or code-block nodes", () => {
    const editor = createTiptapMarkdownEditor({
      element: document.createElement("div"),
      content: "plain text",
      placeholder: "Material",
      onUpdate: vi.fn()
    });

    expect(editor.hasNode("image")).toBe(false);
    expect(editor.hasNode("codeBlock")).toBe(false);
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
