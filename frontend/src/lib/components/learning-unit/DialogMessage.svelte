<script lang="ts">
  import MarkdownContent from "$lib/components/ui/MarkdownContent.svelte";

  let { kind, speaker = "", markdown, current = false, usedStarter = false }: {
    kind: "ai" | "student";
    speaker?: string;
    markdown: string;
    current?: boolean;
    usedStarter?: boolean;
  } = $props();
</script>

<article
  class={`dialog-message dialog-message--${kind}`}
  class:dialog-message--current={kind === "ai" && current}
  aria-label={kind === "ai" && current ? "Aktuelle Frage" : undefined}
>
  <p class="dialog-message__speaker">{kind === "ai" ? speaker : "Du"}</p>
  <div class="dialog-message__bubble markdown-prose">
    <MarkdownContent source={markdown} style="display: contents" />
    {#if kind === "student" && usedStarter}<small class="dialog-message__help">Hilfestellung: Satzanfang verwendet</small>{/if}
  </div>
</article>
