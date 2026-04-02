<script lang="ts">
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
  <button class="learning-work-item__toggle" type="button" onclick={() => onToggle?.()}>
    <div class="learning-work-item__header">
      <div class="learning-work-item__copy">
        <div class="learning-work-item__kicker-row">
          {#if contextLabel}
            <span class="learning-work-item__context">{contextLabel}</span>
          {/if}
          <span class="learning-work-item__kicker">{kindLabel()}</span>
        </div>
        <h4>{material.title}</h4>
      </div>

      <span class:learning-work-item__toggle-icon--expanded={expanded} class="learning-work-item__toggle-icon" aria-hidden="true">
        ▾
      </span>
    </div>
  </button>

  {#if expanded}
    <div class="learning-work-item__body">
      {#if material.kind === "markdown"}
        <pre>{material.body_md}</pre>
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
