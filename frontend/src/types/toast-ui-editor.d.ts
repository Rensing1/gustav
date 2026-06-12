declare module "@toast-ui/editor" {
  export interface EditorOptions {
    el: HTMLElement;
    height?: string;
    minHeight?: string;
    initialValue?: string;
    initialEditType?: "markdown" | "wysiwyg";
    hideModeSwitch?: boolean;
    usageStatistics?: boolean;
    autofocus?: boolean;
    language?: string;
    placeholder?: string;
    toolbarItems?: string[][];
  }

  export class Editor {
    constructor(options: EditorOptions);
    on(type: "change", handler: () => void): void;
    getMarkdown(): string;
    setMarkdown(markdown: string, cursorToEnd?: boolean): void;
    destroy(): void;
  }

  export default Editor;
}

declare module "@toast-ui/editor/dist/i18n/de-de";
