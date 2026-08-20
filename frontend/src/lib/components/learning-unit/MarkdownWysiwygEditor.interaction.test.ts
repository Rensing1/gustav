import { act, render } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

const fakeEditor = vi.hoisted(() => ({
  markdown: "",
  onUpdate: null as ((value: string) => void) | null,
  getMarkdown: vi.fn(() => fakeEditor.markdown),
  setMarkdown: vi.fn((value: string) => {
    fakeEditor.markdown = value;
  }),
  setEditable: vi.fn(),
  destroy: vi.fn()
}));

vi.mock("./tiptap-markdown-editor", () => ({
  createTiptapMarkdownEditor: vi.fn((options: { content: string; onUpdate: (value: string) => void }) => {
    fakeEditor.markdown = options.content;
    fakeEditor.onUpdate = options.onUpdate;
    return {
      getMarkdown: fakeEditor.getMarkdown,
      setMarkdown: fakeEditor.setMarkdown,
      setEditable: fakeEditor.setEditable,
      setBlockType: vi.fn(),
      toggleBold: vi.fn(),
      toggleItalic: vi.fn(),
      toggleBulletList: vi.fn(),
      toggleOrderedList: vi.fn(),
      setLink: vi.fn(() => true),
      insertTable: vi.fn(),
      addRowAfter: vi.fn(),
      deleteRow: vi.fn(),
      addColumnAfter: vi.fn(),
      deleteColumn: vi.fn(),
      deleteTable: vi.fn(),
      isActive: vi.fn(() => false),
      hasNode: vi.fn(() => true),
      destroy: fakeEditor.destroy
    };
  })
}));

import MarkdownWysiwygEditor from "./MarkdownWysiwygEditor.svelte";

describe("MarkdownWysiwygEditor interaction", () => {
  beforeEach(() => {
    fakeEditor.markdown = "";
    fakeEditor.onUpdate = null;
    fakeEditor.getMarkdown.mockClear();
    fakeEditor.setMarkdown.mockClear();
    fakeEditor.setEditable.mockClear();
    fakeEditor.destroy.mockClear();
  });

  it("does not serialize or replace an editor value echoed back by its parent", async () => {
    const onInput = vi.fn();
    const { rerender } = render(MarkdownWysiwygEditor, {
      props: { value: "", onInput }
    });
    await vi.waitFor(() => expect(fakeEditor.onUpdate).not.toBeNull());
    fakeEditor.getMarkdown.mockClear();
    fakeEditor.setMarkdown.mockClear();

    await act(() => {
      fakeEditor.markdown = "Neuer Entwurf";
      fakeEditor.onUpdate?.("Neuer Entwurf");
    });
    await rerender({ value: "Neuer Entwurf", onInput });

    expect(onInput).toHaveBeenCalledWith("Neuer Entwurf");
    expect(fakeEditor.getMarkdown).not.toHaveBeenCalled();
    expect(fakeEditor.setMarkdown).not.toHaveBeenCalled();
  });
});
