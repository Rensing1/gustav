<script lang="ts">
  import { getContext } from "svelte";
  import type { HTMLAttributes } from "svelte/elements";
  import { markdownDocument, type MarkdownPart } from "$lib/utils/markdown";
  import { renderDiagrams, type DiagramResult } from "$lib/utils/diagrams";
  import { themeContextKey, type ThemeReader } from "$lib/theme/context";

  let { source, theme, ...attributes }: HTMLAttributes<HTMLDivElement> & {
    source: string | null | undefined;
    theme?: "light" | "dark";
  } = $props();
  const readTheme = getContext<ThemeReader | undefined>(themeContextKey);
  const document = $derived(markdownDocument(source));
  const resolvedTheme = $derived(theme ?? readTheme?.() ?? "light");
  let results = $state<DiagramResult[]>([]);
  let failed = $state(false);

  $effect(() => {
    const sources = document.diagrams;
    const currentTheme = resolvedTheme;
    results = [];
    failed = false;
    if (!sources.length) return;
    const controller = new AbortController();
    renderDiagrams(sources, currentTheme, controller.signal).then((next) => {
      if (!controller.signal.aborted) results = next;
    }).catch(() => {
      if (!controller.signal.aborted) failed = true;
    });
    return () => controller.abort();
  });
</script>

{#snippet content(parts: MarkdownPart[])}
  {#each parts as part}
    {#if part.kind === "html"}
      {@html part.html}
    {:else if part.kind === "container"}
      <svelte:element this={part.tag}>{@render content(part.children)}</svelte:element>
    {:else}
      {@const result = results[part.index]}
      <figure class="markdown-diagram" class:markdown-diagram--rendered={result && "png" in result}>
        {#if result && "png" in result}
          <div class="markdown-diagram__image" data-theme={resolvedTheme}>
            <img src={`data:image/png;base64,${result.png}`} width={result.width} height={result.height} alt="Mermaid-Diagramm" />
          </div>
        {:else if failed || result}
          <p role="status">{failed ? "Der Diagrammdienst ist vorübergehend nicht verfügbar." : "Das Diagramm konnte nicht dargestellt werden."} Der Quelltext bleibt erhalten.</p>
        {/if}
        <details open={!result || !("png" in result)}>
          <summary>Quelltext anzeigen</summary>
          <pre><code class="language-mermaid">{part.source}</code></pre>
        </details>
      </figure>
    {/if}
  {/each}
{/snippet}

<div {...attributes} class={["markdown-prose", attributes.class]}>{@render content(document.parts)}</div>
