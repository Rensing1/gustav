<script lang="ts">
  import LearnerMaterialContext from "$lib/components/learning-unit/LearnerMaterialContext.svelte";
  import LearnerFocusedMaterialContext from "$lib/components/learning-unit/LearnerFocusedMaterialContext.svelte";
  import type { LearnerMaterialContextModule } from "$lib/learning-unit/workspace";
  import type { LearningSubmission, SubmissionHistoryLoadState } from "$lib/types/learning";
  import { renderMarkdown } from "$lib/utils/markdown";


  let {
    courseId,
    taskTitle,
    taskKind,
    instructionMd,
    roundCurrent = null,
    roundMaximum = null,
    variant = "task",
    scrollSurface = $bindable(null),
    modules = [],
    expandedModuleIds = [],
    expandedModuleMaterialKeys = {},
    expandedSubmissionModuleIds = [],
    expandedSubmissionKeys = [],
    historyByTask = {},
    historyStateByTask = {},
    focusedModuleId = null,
    closedModuleTitle = null,
    onScroll = null,
    onToggleModule = null,
    onToggleMaterial = null,
    onToggleSubmissionGroup = null,
    onToggleSubmission = null,
    onOpenReference = null,
    onCloseModule = null,
    onUndoCloseModule = null
  }: {
    courseId: string;
    taskTitle: string;
    taskKind: string;
    instructionMd: string;
    roundCurrent?: number | null;
    roundMaximum?: number | null;
    variant?: "task" | "dialog";
    scrollSurface?: HTMLDivElement | null;
    modules?: LearnerMaterialContextModule[];
    expandedModuleIds?: string[];
    expandedModuleMaterialKeys?: Record<string, string[]>;
    expandedSubmissionModuleIds?: string[];
    expandedSubmissionKeys?: string[];
    historyByTask?: Record<string, LearningSubmission[]>;
    historyStateByTask?: Record<string, SubmissionHistoryLoadState>;
    focusedModuleId?: string | null;
    closedModuleTitle?: string | null;
    onScroll?: ((scrollTop: number) => void) | null;
    onToggleModule?: ((moduleId: string) => void | Promise<void>) | null;
    onToggleMaterial?: ((moduleId: string, referenceKey: string) => void) | null;
    onToggleSubmissionGroup?: ((moduleId: string) => void | Promise<void>) | null;
    onToggleSubmission?: ((referenceKey: string) => void) | null;
    onOpenReference?: ((referenceKey: string) => void | Promise<void>) | null;
    onCloseModule?: ((moduleId: string) => void) | null;
    onUndoCloseModule?: (() => void) | null;
  } = $props();

  let showAllMaterials = $state(false);

  function additionalModules(): LearnerMaterialContextModule[] {
    const activeModuleId = focusedModuleId
      ?? modules.find((module) => module.current)?.id
      ?? modules[0]?.id
      ?? null;

    return modules.flatMap((module) => {
      if (module.id !== activeModuleId) return [module];

      // The active module's materials are already shown directly above. Keep
      // only its own submissions in the additional context to avoid duplicates.
      const submissionItems = module.items.filter((item) => item.kind === "task" && item.task?.has_submission);
      return submissionItems.length ? [{ ...module, items: submissionItems }] : [];
    });
  }
</script>

<aside
  class:dialog-sidebar={variant === "dialog"}
  class="learner-task-context"
  data-work-surface={variant === "task" ? "materials" : undefined}
  data-dialog-surface={variant === "dialog" ? "materials" : undefined}
  aria-label="Aufgabe und Kontext"
>
  <div
    bind:this={scrollSurface}
    class="learner-task-context__scroll"
    onscroll={(event) => onScroll?.(event.currentTarget.scrollTop)}
  >
    <header class="learner-task-context__header">
      <div class="learner-task-context__headline">
        <div class="learner-task-context__title">
          <h2>{taskTitle}</h2>
          <span>{taskKind}</span>
        </div>
        {#if roundCurrent !== null && roundMaximum !== null}
          <section class="learner-task-context__progress" aria-label="Gesprächsfortschritt">
            <div
              class="learner-task-context__progress-ring"
              role="progressbar"
              aria-label={`Runde ${roundCurrent} von ${roundMaximum}`}
              aria-valuemin="0"
              aria-valuemax={roundMaximum}
              aria-valuenow={roundCurrent}
            ></div>
            <span>Runde {roundCurrent} von {roundMaximum}</span>
          </section>
        {/if}
      </div>
      <div class="learner-task-context__assignment">
        <h3>Aufgabe</h3>
        <div class="learner-task-context__instruction">
          {@html renderMarkdown(instructionMd)}
        </div>
      </div>
    </header>

    <LearnerFocusedMaterialContext
      {modules}
      {focusedModuleId}
      {expandedModuleMaterialKeys}
      {onToggleMaterial}
      {onOpenReference}
    />

    <details class="learner-task-context__all-materials">
      <summary onclick={() => showAllMaterials = !showAllMaterials}>Weitere Materialien und eigene Abgaben</summary>
      {#if showAllMaterials}
        <LearnerMaterialContext
          {courseId}
          modules={additionalModules()}
          compactRows={true}
          {expandedModuleIds}
          {expandedModuleMaterialKeys}
          {expandedSubmissionModuleIds}
          {expandedSubmissionKeys}
          {historyByTask}
          {historyStateByTask}
          {focusedModuleId}
          {closedModuleTitle}
          {onToggleModule}
          {onToggleMaterial}
          {onToggleSubmissionGroup}
          {onToggleSubmission}
          {onOpenReference}
          {onCloseModule}
          {onUndoCloseModule}
        />
      {/if}
    </details>
  </div>
</aside>
