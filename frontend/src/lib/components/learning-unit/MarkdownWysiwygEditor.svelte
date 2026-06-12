<script lang="ts">
  import { browser } from "$app/environment";
  import { onDestroy, onMount } from "svelte";
  import type { Editor as ToastEditor, EditorOptions } from "@toast-ui/editor";

  import "@toast-ui/editor/dist/toastui-editor.css";

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
  let editor = $state<ToastEditor | null>(null);
  let currentValue = $state("");
  let lastPropValue = $state("");
  let propValueInitialized = $state(false);
  let fallbackValue = $derived(propValueInitialized ? currentValue : String(value || ""));
  let editorReady = $state(false);
  let removeFormListeners: (() => void) | null = null;

  function setCurrentValue(nextValue: string, notify = true) {
    currentValue = nextValue;
    if (notify) {
      onInput?.(nextValue);
    }
  }

  function syncEditorValue() {
    if (!editor) {
      return currentValue;
    }
    const nextValue = editor.getMarkdown();
    if (nextValue !== currentValue) {
      setCurrentValue(nextValue);
    }
    return nextValue;
  }

  function wireFormSync() {
    const form = host?.closest("form");
    if (!form) {
      return;
    }

    const handleSubmit = () => {
      syncEditorValue();
    };
    const handleFormData = (event: Event) => {
      const nextValue = syncEditorValue();
      const formData = (event as Event & { formData?: FormData }).formData;
      formData?.set(name, nextValue);
    };

    form.addEventListener("submit", handleSubmit);
    form.addEventListener("formdata", handleFormData);
    removeFormListeners = () => {
      form.removeEventListener("submit", handleSubmit);
      form.removeEventListener("formdata", handleFormData);
    };
  }

  async function mountEditor() {
    if (!browser || !host || editor) {
      return;
    }

    try {
      await import("@toast-ui/editor/dist/i18n/de-de");
      const module = await import("@toast-ui/editor");
      const EditorCtor = module.default;
      const options: EditorOptions = {
        el: host,
        // Toast UI parses these values as pixel numbers internally, so keep them in px.
        height: "448px",
        minHeight: "352px",
        initialValue: fallbackValue,
        initialEditType: "wysiwyg",
        hideModeSwitch: true,
        usageStatistics: false,
        autofocus: false,
        language: "de-DE",
        placeholder,
        toolbarItems: [
          ["heading", "bold", "italic", "table"],
          ["ul", "ol", "link"]
        ]
      };
      const instance = new EditorCtor(options);

      instance.on("change", () => {
        const nextValue = instance.getMarkdown();
        if (nextValue === currentValue) {
          return;
        }
        setCurrentValue(nextValue);
      });

      editor = instance;
      editorReady = true;
      wireFormSync();
    } catch {
      editorReady = false;
    }
  }

  onMount(() => {
    void mountEditor();
  });

  onDestroy(() => {
    removeFormListeners?.();
    editor?.destroy();
  });

  $effect(() => {
    const nextValue = String(value || "");
    if (propValueInitialized && nextValue === lastPropValue) {
      return;
    }
    propValueInitialized = true;
    lastPropValue = nextValue;
    currentValue = nextValue;
    if (editor && editor.getMarkdown() !== nextValue) {
      editor.setMarkdown(nextValue, false);
    }
  });
</script>

<div class="learning-markdown-editor">
  <div bind:this={host} class="learning-markdown-editor__surface"></div>
  <textarea
    aria-label={name}
    hidden={editorReady}
    name={editorReady ? undefined : name}
    rows="12"
    value={fallbackValue}
    {placeholder}
    oninput={(event) => setCurrentValue((event.currentTarget as HTMLTextAreaElement).value)}
  ></textarea>
  <input type="hidden" name={editorReady ? name : undefined} value={currentValue} />
</div>
