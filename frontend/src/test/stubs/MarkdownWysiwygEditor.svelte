<script lang="ts">
  let {
    name = "text_body",
    value = "",
    placeholder = "",
    onInput = null
  }: {
    name?: string;
    value?: string;
    placeholder?: string;
    onInput?: ((nextValue: string) => void) | null;
  } = $props();
</script>

<label>
  <span>{placeholder}</span>
  <textarea
    aria-label={name}
    value={value}
    oninput={(event) => onInput?.((event.currentTarget as HTMLTextAreaElement).value)}
  ></textarea>
</label>
