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

  function fileMeta(): string {
    return material.filename_original || material.mime_type || "Datei-Material";
  }

  function hasPreviewUrl(): boolean {
    return material.kind === "file" && Boolean(material.file_url);
  }

  function showsInlinePreview(): boolean {
    return (
      hasPreviewUrl() &&
      (material.mime_type?.startsWith("image/") === true || material.mime_type === "application/pdf")
    );
  }

  let simulationRunning = $state(false);
  let simulationRevision = $state(0);

  function resetSimulation(): void {
    simulationRevision += 1;
  }

  function closeSimulation(): void {
    simulationRunning = false;
  }

  const bodyId = $derived(`material-body-${material.id}`);
</script>

<article class:learning-work-item--collapsed={!expanded} class="learning-work-item learning-work-item--material" id={domId}>
  <button
    class:learning-work-item__toggle--collapsed={!expanded}
    class="learning-work-item__toggle"
    type="button"
    title={material.title}
    aria-expanded={expanded}
    aria-controls={bodyId}
    onclick={() => onToggle?.()}
  >
    <div class="learning-material-card__header-inner">
      <div class="learning-work-item__header">
        <span class="learning-work-item__title">{material.title}</span>

        <span class:learning-work-item__toggle-icon--expanded={expanded} class="learning-work-item__toggle-icon" aria-hidden="true">
          <svg viewBox="0 0 20 20">
            <path d="M6.25 8.25 10 12l3.75-3.75" />
          </svg>
        </span>
      </div>
    </div>
  </button>

  {#if expanded}
    <div class="learning-work-item__body" id={bodyId}>
      <div class="learning-material-card__body-inner">
        {#if material.kind === "markdown"}
          <div class="markdown-prose learning-material-prose">
            {@html renderMarkdown(material.body_md)}
          </div>
        {:else if material.kind === "simulation"}
          <section class="learning-material-simulation">
            {#if material.body_md?.trim()}
              <div class="markdown-prose learning-material-prose learning-material-simulation__orientation">
                {@html renderMarkdown(material.body_md)}
              </div>
            {/if}
            {#if material.simulation_url}
              {#if simulationRunning}
                <div class="learning-material-simulation__actions" aria-label="Simulationssteuerung">
                  <button type="button" onclick={resetSimulation}>Zurücksetzen</button>
                  <button type="button" onclick={closeSimulation}>Simulation schließen</button>
                  <a href={material.simulation_url} target="_blank" rel="noreferrer">Separat öffnen</a>
                </div>
                {#key simulationRevision}
                  <iframe
                    class="learning-material-simulation__frame"
                    src={material.simulation_url}
                    title={`Simulation ${material.title}`}
                    sandbox="allow-scripts"
                    referrerpolicy="no-referrer"
                    loading="lazy"
                  ></iframe>
                {/key}
              {:else}
                <button class="learning-material-simulation__start" type="button" onclick={() => (simulationRunning = true)}>
                  Simulation starten
                </button>
              {/if}
            {:else}
              <p class="learning-work-item__file-meta">Simulation derzeit nicht verfügbar.</p>
            {/if}
          </section>
        {:else}
          <section class="learning-material-card__support learning-material-card__support--open">
            {#if hasPreviewUrl() && material.mime_type?.startsWith("image/")}
              <img alt="Materialvorschau" class="learning-material-file__image" loading="lazy" src={material.file_url ?? undefined} />
            {:else if hasPreviewUrl() && material.mime_type === "application/pdf"}
              <iframe
                class="learning-material-file__frame"
                src={material.file_url ?? undefined}
                title={`Material ${material.title}`}
                loading="lazy"
              ></iframe>
            {/if}
            {#if !showsInlinePreview()}
              <p class="learning-work-item__file-meta">{fileMeta()}</p>
            {/if}
            {#if hasPreviewUrl() && !showsInlinePreview()}
              <a class="learning-work-item__link" href={material.file_url ?? undefined}>Datei öffnen</a>
            {/if}
            {#if hasPreviewUrl() && showsInlinePreview()}
              <a class="learning-work-item__link" href={material.file_url ?? undefined} target="_blank" rel="noreferrer">Separat öffnen</a>
            {/if}
          </section>
        {/if}
      </div>
    </div>
  {/if}
</article>
