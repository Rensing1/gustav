<script lang="ts">
  import { browser } from "$app/environment";
  import { onDestroy, onMount } from "svelte";

  import "@toast-ui/editor/dist/toastui-editor.css";

  type MarkdownEditor = {
    on(type: "change", handler: () => void): void;
    getMarkdown(): string;
    setMarkdown(markdown: string, cursorToEnd?: boolean): void;
    destroy(): void;
  };

  let {
    name = "text_body",
    value = "",
    placeholder = "Schreibe hier deine Lösung.",
    onInput = null
  }: {
    name?: string;
    value?: string;
    placeholder?: string;
    onInput?: ((nextValue: string) => void) | null;
  } = $props();

  let host = $state<HTMLDivElement | null>(null);
  let editor = $state<MarkdownEditor | null>(null);
  let currentValue = $state("");

  async function mountEditor() {
    if (!browser || !host || editor) {
      return;
    }

    await import("@toast-ui/editor/dist/i18n/de-de");
    const module = (await import("@toast-ui/editor")) as unknown as {
      default: new (options: Record<string, unknown>) => MarkdownEditor;
    };
    const EditorCtor = module.default;
    const instance = new EditorCtor({
      el: host,
      height: "28rem",
      minHeight: "22rem",
      initialValue: currentValue,
      initialEditType: "wysiwyg",
      hideModeSwitch: true,
      usageStatistics: false,
      autofocus: false,
      language: "de-DE",
      placeholder,
      toolbarItems: [
        ["heading", "bold", "italic"],
        ["ul", "ol", "link"]
      ]
    });

    instance.on("change", () => {
      const nextValue = instance.getMarkdown();
      if (nextValue === currentValue) {
        return;
      }
      currentValue = nextValue;
      onInput?.(nextValue);
    });

    editor = instance;
  }

  onMount(() => {
    currentValue = String(value || "");
    void mountEditor();
  });

  onDestroy(() => {
    editor?.destroy();
  });

  $effect(() => {
    const nextValue = String(value || "");
    if (nextValue === currentValue) {
      return;
    }
    currentValue = nextValue;
    if (editor && editor.getMarkdown() !== nextValue) {
      editor.setMarkdown(nextValue, false);
    }
  });
</script>

<div class="learning-markdown-editor">
  <div bind:this={host} class="learning-markdown-editor__surface"></div>
  <input type="hidden" {name} value={currentValue} />
</div>
