<script lang="ts">
  import WorkspaceOutline from "$lib/components/ui/WorkspaceOutline.svelte";
  import LearningMaterialCard from "./LearningMaterialCard.svelte";
  import type { LearnerMaterialContextModule } from "$lib/learning-unit/workspace";
  import type { LearningSubmission, SubmissionHistoryLoadState } from "$lib/types/learning";
  import MarkdownContent from "$lib/components/ui/MarkdownContent.svelte";


  let {
    courseId,
    taskId,
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
    onOpenCurrentTask = null,
    onCloseModule = null,
    onUndoCloseModule = null
  }: {
    courseId: string;
    taskId: string;
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
    onOpenCurrentTask?: (() => void) | null;
    onOpenReference?: ((referenceKey: string) => void | Promise<void>) | null;
    onCloseModule?: ((moduleId: string) => void) | null;
    onUndoCloseModule?: (() => void) | null;
  } = $props();

  const navigationGroups = $derived(modules.map((module) => ({
    id: module.id,
    title: module.title,
    status: module.loading ? "Inhalte werden geladen …"
      : module.error ? "Materialien konnten nicht geladen werden."
      : module.loaded && !module.items.some((item) => item.kind === "material" || item.task?.id === taskId || item.task?.has_submission)
        ? "Keine Materialien oder eigenen Abgaben." : undefined,
    items: module.items.filter((item) => item.kind === "material" || item.task?.id === taskId || item.task?.has_submission)
      .sort((left, right) => Number(left.kind === "task") - Number(right.kind === "task"))
      .flatMap<{ key: string; title: string; kind: "material" | "task"; expanded?: boolean; contentId?: string }>((item) => {
        if (item.kind === "material") return [{
          key: item.key, title: item.title, kind: item.kind,
          expanded: expandedModuleMaterialKeys[module.id]?.includes(item.key) ?? false,
          contentId: `task-context-${taskId}-${item.key.replace(/[^a-zA-Z0-9_-]+/g, "-")}`
        }];
        // Keep the current task distinct from its previously submitted answer.
        const entries: Array<{ key: string; title: string; kind: "task" }> = [];
        if (item.task?.id === taskId) entries.push({ key: item.key, title: item.title, kind: "task" });
        if (item.task?.has_submission) entries.push({ key: `submission:${item.task.id}`, title: `${item.title} · ${item.task.latest_final_submission_at || item.task.latest_submission_intent === "submit" ? "Meine Abgabe" : "Mein Entwurf"}`, kind: "task" });
        return entries;
      })
  })));

  function expandModule(moduleId: string) {
    if (!expandedModuleIds.includes(moduleId)) void onToggleModule?.(moduleId);
  }

  /** Toggle permitted material inline; keep task navigation and submission reading distinct.
   * The key comes from the already authorized module contents, never a new content lookup.
   */
  function openReference(key: string) {
    if (key === `task:${taskId}`) {
      onOpenCurrentTask?.();
      return;
    }
    // Material disclosure uses the same persisted state as the rest of the workspace.
    const module = modules.find((module) => module.items.some((item) => item.kind === "material" && item.key === key));
    if (module) {
      onToggleMaterial?.(module.id, key);
      return;
    }
    void onOpenReference?.(key);
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
          <h2>Aufgabenstellung</h2>
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
        <MarkdownContent class="learner-task-context__instruction" source={instructionMd} />
      </div>
    </header>

    <WorkspaceOutline
      title="Inhalt"
      groups={navigationGroups}
      embedded
      initialGroupId={modules.find((module) => module.current)?.id ?? focusedModuleId ?? null}
      activeItemKeys={[`task:${taskId}`]}
      onExpandGroup={expandModule}
      onOpenItem={openReference}
      onRemoveGroup={onCloseModule ?? undefined}
    >
      {#snippet itemContent(key)}
        {@const item = modules.flatMap((module) => module.items).find((item) => item.key === key)}
        {#if item?.material}
          <LearningMaterialCard material={item.material} embedded domId={`task-context-viewer-${taskId}-${item.material.id}`} />
          {#if onOpenReference}
            <button
              id={`reference-reader-trigger-${key.replace(/[^a-zA-Z0-9_-]+/g, "-")}`}
              class="workspace-link-action"
              type="button"
              aria-label={`${item.title} groß lesen`}
              onclick={() => onOpenReference?.(key)}
            >Groß lesen</button>
          {/if}
        {:else}
          <p class="workspace-note">Material derzeit nicht verfügbar.</p>
        {/if}
      {/snippet}
    </WorkspaceOutline>
    {#if closedModuleTitle && onUndoCloseModule}
      <button class="workspace-link-action" type="button" onclick={() => onUndoCloseModule?.()}>{closedModuleTitle} wieder öffnen</button>
    {/if}
  </div>
</aside>
