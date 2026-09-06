<script lang="ts">
  import { renderMarkdown } from "$lib/utils/markdown";

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
  {#if kind === "ai"}<p class="dialog-message__speaker">{speaker}</p>{/if}
  <div class="dialog-message__bubble markdown-prose">
    {@html renderMarkdown(markdown)}
    {#if kind === "student" && usedStarter}<small class="dialog-message__help">Hilfestellung: Satzanfang verwendet</small>{/if}
  </div>
  {#if kind === "student"}
    <!-- Technical learner subjects must never become visible avatar labels. -->
    <span class="dialog-message__avatar" aria-label="Du">D</span>
  {/if}
</article>
