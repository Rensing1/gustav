<script lang="ts">
  import { browser } from "$app/environment";
  import { onDestroy, onMount } from "svelte";
  import type { TiptapMarkdownEditor } from "./tiptap-markdown-editor";

  let {
    name = "text_body",
    value = "",
    placeholder = "Schreibe hier deine Lösung.",
    ariaLabel = name,
    disabled = false,
    focusRequest = 0,
    onInput = null
  }: {
    name?: string;
    value?: string;
    placeholder?: string;
    ariaLabel?: string;
    disabled?: boolean;
    focusRequest?: number;
    onInput?: ((nextValue: string) => void) | null;
  } = $props();

  let host = $state<HTMLDivElement | null>(null);
  let fallbackTextarea = $state<HTMLTextAreaElement | null>(null);
  let editor = $state<TiptapMarkdownEditor | null>(null);
  let currentValue = $state("");
  let lastPropValue = $state("");
  let propValueInitialized = $state(false);
  let fallbackValue = $derived(propValueInitialized ? currentValue : String(value || ""));
  let editorReady = $state(false);
  let editorRevision = $state(0);
  let linkPanelOpen = $state(false);
  let linkValue = $state("");
  let linkError = $state("");
  let appliedDisabled = $state<boolean | null>(null);
  let handledFocusRequest = $state(0);
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

    const handleSubmit = () => syncEditorValue();
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

  function run(command: (activeEditor: TiptapMarkdownEditor) => void) {
    if (!editor || disabled) {
      return;
    }
    command(editor);
    editorRevision += 1;
  }

  function isActive(name: string, attributes?: Record<string, unknown>) {
    void editorRevision;
    return editor?.isActive(name, attributes) ?? false;
  }

  function applyLink() {
    if (disabled || !editor?.setLink(linkValue)) {
      linkError = "Bitte eine vollständige http- oder https-Adresse eingeben.";
      return;
    }
    linkError = "";
    linkPanelOpen = false;
    editorRevision += 1;
  }

  async function mountEditor() {
    if (!browser || !host || editor) {
      return;
    }

    try {
      const { createTiptapMarkdownEditor } = await import("./tiptap-markdown-editor");
      editor = createTiptapMarkdownEditor({
        element: host,
        content: fallbackValue,
        placeholder,
        ariaLabel,
        editable: !disabled,
        onUpdate: (nextValue) => {
          if (nextValue !== currentValue) {
            setCurrentValue(nextValue);
          }
        },
        onStateChange: () => {
          editorRevision += 1;
        }
      });
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
    const editorValueAlreadyCurrent = nextValue === currentValue;
    propValueInitialized = true;
    lastPropValue = nextValue;
    currentValue = nextValue;
    // Tiptap already owns values it emitted; serializing them again blocks touch keyboards on long drafts.
    if (editor && !editorValueAlreadyCurrent && editor.getMarkdown() !== nextValue) {
      editor.setMarkdown(nextValue);
    }
  });

  $effect(() => {
    const activeEditor = editor;
    const nextDisabled = disabled;
    if (activeEditor && appliedDisabled !== nextDisabled) {
      appliedDisabled = nextDisabled;
      activeEditor.setEditable(!nextDisabled);
    }
    if (nextDisabled) {
      linkPanelOpen = false;
    }
  });

  $effect(() => {
    const requested = focusRequest;
    if (requested <= handledFocusRequest || disabled) {
      return;
    }
    handledFocusRequest = requested;
    if (editor) {
      host?.querySelector<HTMLElement>('[contenteditable="true"]')?.focus({ preventScroll: true });
    } else {
      fallbackTextarea?.focus({ preventScroll: true });
    }
  });
</script>

<div class:learning-markdown-editor--disabled={disabled} class="learning-markdown-editor">
  <fieldset class="learning-markdown-editor__controls" disabled={disabled}>
    {#if editorReady}
      <div class="learning-markdown-editor__toolbar" role="toolbar" aria-label="Text formatieren">
      <select
        aria-label="Absatzformat"
        onchange={(event) => {
          const selected = Number((event.currentTarget as HTMLSelectElement).value);
          run((activeEditor) => activeEditor.setBlockType(selected === 0 ? null : selected as 1 | 2 | 3));
        }}
      >
        <option value="0">Absatz</option>
        <option value="1">Überschrift 1</option>
        <option value="2">Überschrift 2</option>
        <option value="3">Überschrift 3</option>
      </select>
      <button type="button" class:active={isActive("bold")} aria-label="Fett" onclick={() => run((item) => item.toggleBold())}><strong>F</strong></button>
      <button type="button" class:active={isActive("italic")} aria-label="Kursiv" onclick={() => run((item) => item.toggleItalic())}><em>K</em></button>
      <button type="button" class:active={isActive("bulletList")} onclick={() => run((item) => item.toggleBulletList())}>Liste</button>
      <button type="button" class:active={isActive("orderedList")} onclick={() => run((item) => item.toggleOrderedList())}>Nummerierung</button>
      <button type="button" class:active={isActive("link")} onclick={() => { linkPanelOpen = !linkPanelOpen; linkError = ""; }}>Link</button>
      <button type="button" onclick={() => run((item) => item.insertTable())}>Tabelle</button>
      {#if isActive("table")}
        <span class="learning-markdown-editor__table-actions" aria-label="Tabelle bearbeiten">
          <button type="button" onclick={() => run((item) => item.addRowAfter())}>Zeile +</button>
          <button type="button" onclick={() => run((item) => item.deleteRow())}>Zeile −</button>
          <button type="button" onclick={() => run((item) => item.addColumnAfter())}>Spalte +</button>
          <button type="button" onclick={() => run((item) => item.deleteColumn())}>Spalte −</button>
          <button type="button" onclick={() => run((item) => item.deleteTable())}>Tabelle löschen</button>
        </span>
      {/if}
      </div>
      {#if linkPanelOpen}
        <div class="learning-markdown-editor__link-panel">
          <label for={`${name}-link`}>Link-Adresse</label>
          <input id={`${name}-link`} type="url" bind:value={linkValue} placeholder="https://example.org" onkeydown={(event) => { if (event.key === "Enter") { event.preventDefault(); applyLink(); } }} />
          <button type="button" onclick={applyLink}>Übernehmen</button>
          <button type="button" onclick={() => { linkValue = ""; applyLink(); }}>Entfernen</button>
          {#if linkError}<span class="learning-markdown-editor__link-error">{linkError}</span>{/if}
        </div>
      {/if}
    {/if}
  </fieldset>
  <div bind:this={host} class="learning-markdown-editor__surface"></div>
  <textarea
    bind:this={fallbackTextarea}
    aria-label={editorReady ? undefined : ariaLabel}
    hidden={editorReady}
    name={editorReady ? undefined : name}
    rows="12"
    value={fallbackValue}
    {placeholder}
    {disabled}
    oninput={(event) => setCurrentValue((event.currentTarget as HTMLTextAreaElement).value)}
  ></textarea>
  <input type="hidden" name={editorReady ? name : undefined} value={currentValue} />
</div>
