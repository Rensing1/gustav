import { Editor } from "@tiptap/core";
import Placeholder from "@tiptap/extension-placeholder";
import { TableKit } from "@tiptap/extension-table";
import { Markdown } from "@tiptap/markdown";
import StarterKit from "@tiptap/starter-kit";

type HeadingLevel = 1 | 2 | 3;

export type TiptapMarkdownEditor = {
  getMarkdown: () => string;
  setMarkdown: (markdown: string, notify?: boolean) => void;
  setEditable: (editable: boolean) => void;
  setBlockType: (level: HeadingLevel | null) => void;
  toggleBold: () => void;
  toggleItalic: () => void;
  toggleBulletList: () => void;
  toggleOrderedList: () => void;
  setLink: (href: string) => boolean;
  insertTable: () => void;
  addRowAfter: () => void;
  deleteRow: () => void;
  addColumnAfter: () => void;
  deleteColumn: () => void;
  deleteTable: () => void;
  isActive: (name: string, attributes?: Record<string, unknown>) => boolean;
  hasNode: (name: string) => boolean;
  destroy: () => void;
};

type CreateEditorOptions = {
  element: HTMLElement;
  content: string;
  placeholder: string;
  ariaLabel?: string;
  editable?: boolean;
  onUpdate: (markdown: string) => void;
  onStateChange?: () => void;
};

/**
 * Adapt Tiptap's document model to GUSTAV's existing Markdown form contract.
 * The schema deliberately excludes executable/code and image nodes; callers
 * must still render persisted Markdown through the central sanitizer.
 */
export function createTiptapMarkdownEditor(options: CreateEditorOptions): TiptapMarkdownEditor {
  const editor = new Editor({
    element: options.element,
    content: options.content,
    contentType: "markdown",
    editable: options.editable ?? true,
    extensions: [
      StarterKit.configure({
        blockquote: false,
        code: false,
        codeBlock: false,
        horizontalRule: false,
        strike: false,
        link: {
          autolink: false,
          openOnClick: false,
          defaultProtocol: "https",
          protocols: ["http", "https"]
        }
      }),
      TableKit.configure({ table: { resizable: false } }),
      Placeholder.configure({ placeholder: options.placeholder }),
      Markdown
    ],
    editorProps: {
      attributes: {
        "aria-label": options.ariaLabel ?? options.placeholder,
        class: "tiptap"
      }
    },
    onUpdate: ({ editor: activeEditor }) => {
      options.onUpdate(activeEditor.getMarkdown());
      options.onStateChange?.();
    },
    onSelectionUpdate: () => options.onStateChange?.()
  });

  const focus = () => editor.chain().focus();

  return {
    getMarkdown: () => editor.getMarkdown(),
    setMarkdown(markdown, notify = false) {
      editor.commands.setContent(markdown, { contentType: "markdown", emitUpdate: notify });
    },
    setEditable(editable) {
      editor.setEditable(editable);
    },
    setBlockType(level) {
      if (level === null) {
        focus().setParagraph().run();
        return;
      }
      focus().setHeading({ level }).run();
    },
    toggleBold: () => void focus().toggleBold().run(),
    toggleItalic: () => void focus().toggleItalic().run(),
    toggleBulletList: () => void focus().toggleBulletList().run(),
    toggleOrderedList: () => void focus().toggleOrderedList().run(),
    setLink(href) {
      const normalizedHref = href.trim();
      if (!normalizedHref) {
        focus().extendMarkRange("link").unsetLink().run();
        return true;
      }
      if (!/^https?:\/\//i.test(normalizedHref)) {
        return false;
      }
      focus().extendMarkRange("link").setLink({ href: normalizedHref }).run();
      return true;
    },
    insertTable: () => void focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run(),
    addRowAfter: () => void focus().addRowAfter().run(),
    deleteRow: () => void focus().deleteRow().run(),
    addColumnAfter: () => void focus().addColumnAfter().run(),
    deleteColumn: () => void focus().deleteColumn().run(),
    deleteTable: () => void focus().deleteTable().run(),
    isActive: (name, attributes) => editor.isActive(name, attributes),
    hasNode: (name) => Boolean(editor.schema.nodes[name]),
    destroy: () => editor.destroy()
  };
}
