<script lang="ts">
  import MarkdownWysiwygEditor from "$lib/components/learning-unit/MarkdownWysiwygEditor.svelte";

  let {
    name = "body_md",
    value = "",
    placeholder = "Text eingeben …",
    ariaLabel = name,
    disabled = false,
    onInput = null
  }: {
    name?: string;
    value?: string;
    placeholder?: string;
    ariaLabel?: string;
    disabled?: boolean;
    onInput?: ((nextValue: string) => void) | null;
  } = $props();
</script>

<!-- This shared entry point keeps authoring and learning forms on one editor contract. -->
<MarkdownWysiwygEditor {name} {value} {placeholder} {ariaLabel} {disabled} {onInput} />
