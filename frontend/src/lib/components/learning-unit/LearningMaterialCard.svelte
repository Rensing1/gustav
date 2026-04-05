<script lang="ts">
  import { renderMarkdown } from "$lib/utils/markdown";
  import type { LearningMaterial } from "$lib/types/learning";

  let {
    material,
    domId = undefined,
    contextLabel = null,
    expanded = true,
    onToggle = null
  }: {
    material: LearningMaterial;
    domId?: string;
    contextLabel?: string | null;
    expanded?: boolean;
    onToggle?: (() => void) | null;
  } = $props();

  function kindLabel(): string {
    if (material.kind === "markdown") {
      return "Material";
    }
    return "Datei";
  }

  function fileMeta(): string {
    return material.filename_original || material.mime_type || "Datei-Material";
  }
</script>

<article class:learning-work-item--collapsed={!expanded} class="learning-work-item learning-work-item--material" id={domId}>
  <button
    class:learning-work-item__toggle--collapsed={!expanded}
    class="learning-work-item__toggle"
    type="button"
    title={material.title}
    onclick={() => onToggle?.()}
  >
    <div class="learning-work-item__header">
      <span class="learning-work-item__title">{material.title}</span>

      <span class:learning-work-item__toggle-icon--expanded={expanded} class="learning-work-item__toggle-icon" aria-hidden="true">
        <svg viewBox="0 0 20 20">
          <path d="M6.25 8.25 10 12l3.75-3.75" />
        </svg>
      </span>
    </div>
  </button>

  {#if expanded}
    <div class="learning-work-item__body">
      {#if material.kind === "markdown"}
        <div class="markdown-prose learning-material-prose">
          {@html renderMarkdown(material.body_md)}
        </div>
      {:else}
        <section class="learning-work-item__support learning-work-item__support--open">
          <header class="learning-work-item__support-header">
            <h5>Datei</h5>
          </header>
          <p class="learning-work-item__file-meta">{fileMeta()}</p>
        </section>
      {/if}
    </div>
  {/if}
</article>
