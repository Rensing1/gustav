<script lang="ts">
  import { tick } from "svelte";

  import LearnerMaterialRow from "$lib/components/learning-unit/LearnerMaterialRow.svelte";
  import LearningReferenceDocument from "$lib/components/learning-unit/LearningReferenceDocument.svelte";
  import StatusMessage from "$lib/components/ui/StatusMessage.svelte";
  import type { LearnerMaterialContextModule } from "$lib/learning-unit/workspace";
  import type { LearningSubmission, SubmissionHistoryLoadState } from "$lib/types/learning";


  let {
    courseId,
    modules = [],
    expandedModuleIds = [],
    expandedModuleMaterialKeys = {},
    expandedSubmissionModuleIds = [],
    expandedSubmissionKeys = [],
    historyByTask = {},
    historyStateByTask = {},
    focusedModuleId = null,
    closedModuleTitle = null,
    compactRows = false,
    onToggleModule = null,
    onToggleMaterial = null,
    onToggleSubmissionGroup = null,
    onToggleSubmission = null,
    onOpenReference = null,
    onCloseModule = null,
    onUndoCloseModule = null
  }: {
    courseId: string;
    modules?: LearnerMaterialContextModule[];
    expandedModuleIds?: string[];
    expandedModuleMaterialKeys?: Record<string, string[]>;
    expandedSubmissionModuleIds?: string[];
    expandedSubmissionKeys?: string[];
    historyByTask?: Record<string, LearningSubmission[]>;
    historyStateByTask?: Record<string, SubmissionHistoryLoadState>;
    focusedModuleId?: string | null;
    closedModuleTitle?: string | null;
    compactRows?: boolean;
    onToggleModule?: ((moduleId: string) => void | Promise<void>) | null;
    onToggleMaterial?: ((moduleId: string, referenceKey: string) => void) | null;
    onToggleSubmissionGroup?: ((moduleId: string) => void | Promise<void>) | null;
    onToggleSubmission?: ((referenceKey: string) => void) | null;
    onOpenReference?: ((referenceKey: string) => void | Promise<void>) | null;
    onCloseModule?: ((moduleId: string) => void) | null;
    onUndoCloseModule?: (() => void) | null;
  } = $props();

  let lastFocusedModuleId = $state<string | null>(null);

  $effect(() => {
    if (!focusedModuleId || focusedModuleId === lastFocusedModuleId) return;
    lastFocusedModuleId = focusedModuleId;
    void tick().then(() => {
      document.getElementById(`learner-context-module-${safeId(focusedModuleId)}`)?.focus({ preventScroll: false });
    });
  });

  function safeId(value: string): string {
    return value.replace(/[^a-zA-Z0-9_-]+/g, "-");
  }

  function moduleExpanded(module: LearnerMaterialContextModule): boolean {
    return compactRows || module.current || expandedModuleIds.includes(module.id);
  }

  function materialItems(module: LearnerMaterialContextModule) {
    return module.items.filter((item) => item.kind === "material" && item.material);
  }

  function submissionItems(module: LearnerMaterialContextModule) {
    return module.items.filter((item) => item.kind === "task" && item.task?.has_submission);
  }

  function materialExpanded(moduleId: string, referenceKey: string, index: number): boolean {
    const stored = expandedModuleMaterialKeys[moduleId];
    return stored ? stored.includes(referenceKey) : index === 0;
  }

  function history(taskId: string): LearningSubmission[] {
    return historyByTask[taskId] ?? [];
  }
</script>

<section class:learner-material-context--compact={compactRows} class="learner-material-context" aria-label="Materialien">
  {#if !compactRows}<h3>Materialien</h3>{/if}

  <div class="learner-material-context__modules">
    {#each modules as module (module.id)}
      {@const materials = materialItems(module)}
      {@const submissions = submissionItems(module)}
      {@const expanded = moduleExpanded(module)}
      <section
        class:learner-material-context__module--current={module.current}
        class="learner-material-context__module"
        data-context-module-id={module.id}
      >
        <header class="learner-material-context__module-header">
          {#if module.current || compactRows}
            <div
              id={`learner-context-module-${safeId(module.id)}`}
              class="learner-material-context__module-toggle learner-material-context__module-toggle--fixed"
              tabindex="-1"
            >
              {#if !compactRows}
                <svg class="learner-tree-chevron learner-tree-chevron--expanded" aria-hidden="true" viewBox="0 0 16 16">
                  <path d="m6 3.5 4.5 4.5L6 12.5" />
                </svg>
              {/if}
              <h4><span>{module.title}</span>{#if module.current}<small>Aktuell</small>{/if}</h4>
            </div>
          {:else}
            <button
              id={`learner-context-module-${safeId(module.id)}`}
              class="learner-material-context__module-toggle"
              type="button"
              aria-label={`Modul ${module.title} ein- oder ausklappen`}
              aria-expanded={expanded}
              onclick={() => onToggleModule?.(module.id)}
            >
              <svg
                class:learner-tree-chevron--expanded={expanded}
                class="learner-tree-chevron"
                aria-hidden="true"
                viewBox="0 0 16 16"
              >
                <path d="m6 3.5 4.5 4.5L6 12.5" />
              </svg>
              <h4><span>{module.title}</span></h4>
            </button>
          {/if}
          {#if module.closable}
            <button
              class="learner-material-context__close"
              type="button"
              title="Modul schließen"
              aria-label={`Modul ${module.title} schließen`}
              onclick={() => onCloseModule?.(module.id)}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 7 10 10M17 7 7 17" /></svg>
            </button>
          {/if}
        </header>

        {#if expanded}
          <div class:learner-material-context__tree-children={!compactRows} class="learner-material-context__module-body">
            {#if module.loading}
              <div class="learner-material-context__tree-item learner-material-context__tree-item--status">
                <p class="workspace-note">Inhalte werden geladen …</p>
              </div>
            {:else if module.error}
              <div class="learner-material-context__tree-item learner-material-context__tree-item--status">
                <StatusMessage tone="error" title="Material nicht verfügbar" description={module.error} />
              </div>
            {:else if module.loaded}
              {#if materials.length}
                <div class="learner-task-context__list">
                  {#each materials as item, index (item.key)}
                    <div class="learner-material-context__tree-item learner-material-context__tree-item--document">
                      {#if compactRows}
                        <LearnerMaterialRow
                          {item}
                          expanded={materialExpanded(module.id, item.key, index)}
                          onToggle={(referenceKey) => onToggleMaterial?.(module.id, referenceKey)}
                          {onOpenReference}
                        />
                      {:else}
                        <LearningReferenceDocument
                          referenceKey={item.key}
                          label={null}
                          title={item.title}
                          material={item.material}
                          expanded={materialExpanded(module.id, item.key, index)}
                          onToggle={(referenceKey) => onToggleMaterial?.(module.id, referenceKey)}
                          onOpenReader={onOpenReference}
                        />
                      {/if}
                    </div>
                  {/each}
                </div>
              {:else if !submissions.length}
                <div class="learner-material-context__tree-item learner-material-context__tree-item--status">
                  <p class="learner-material-context__empty">Keine Materialien</p>
                </div>
              {/if}

              {#if submissions.length}
                <section class="learner-material-context__submissions learner-material-context__tree-item learner-material-context__tree-item--group">
                  <button
                    class="learner-material-context__submissions-toggle"
                    type="button"
                    aria-label={`Eigene Abgaben in ${module.title} ein- oder ausklappen`}
                    aria-expanded={expandedSubmissionModuleIds.includes(module.id)}
                    onclick={() => onToggleSubmissionGroup?.(module.id)}
                  >
                    <svg
                      class:learner-tree-chevron--expanded={expandedSubmissionModuleIds.includes(module.id)}
                      class="learner-tree-chevron"
                      aria-hidden="true"
                      viewBox="0 0 16 16"
                    >
                      <path d="m6 3.5 4.5 4.5L6 12.5" />
                    </svg>
                    <span>Eigene Abgaben</span>
                  </button>

                  {#if expandedSubmissionModuleIds.includes(module.id)}
                    <div class="learner-material-context__submission-list learner-material-context__tree-children learner-material-context__tree-children--nested">
                      {#each submissions as item (item.key)}
                        {@const taskId = item.task?.id ?? ""}
                        {@const state = historyStateByTask[taskId] ?? "not_loaded"}
                        {#if state === "loading" || state === "not_loaded"}
                          <div class="learner-material-context__tree-item learner-material-context__tree-item--status">
                            <p class="workspace-note">Abgabe zu {item.title} wird geladen …</p>
                          </div>
                        {:else if state === "failed"}
                          <div class="learner-material-context__tree-item learner-material-context__tree-item--status">
                            <StatusMessage tone="error" title="Abgabe nicht verfügbar" description={`Die Abgabe zu ${item.title} konnte nicht geladen werden.`} />
                          </div>
                        {:else if history(taskId).length}
                          <div class="learner-material-context__tree-item learner-material-context__tree-item--submission">
                            <LearningReferenceDocument
                              referenceKey={`submission:${taskId}`}
                              label={null}
                              title={item.title}
                              submissions={history(taskId)}
                              {courseId}
                              {taskId}
                              expanded={expandedSubmissionKeys.includes(`submission:${taskId}`)}
                              onToggle={onToggleSubmission}
                              onOpenReader={onOpenReference}
                            />
                          </div>
                        {/if}
                      {/each}
                    </div>
                  {/if}
                </section>
              {/if}
            {/if}
          </div>
        {/if}
      </section>
    {/each}
  </div>

  {#if closedModuleTitle}
    <div class="learner-material-context__undo">
      <StatusMessage
        tone="info"
        title={`Modul „${closedModuleTitle}“ geschlossen.`}
        actionLabel="Rückgängig"
        onAction={() => onUndoCloseModule?.()}
      />
    </div>
  {/if}
</section>
