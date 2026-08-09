<script lang="ts">
  import { tick } from "svelte";
  import LearningMaterialCard from "$lib/components/learning-unit/LearningMaterialCard.svelte";
  import LearnerMaterialContext from "$lib/components/learning-unit/LearnerMaterialContext.svelte";
  import LearningReferenceDocument from "$lib/components/learning-unit/LearningReferenceDocument.svelte";
  import LearningTaskCard from "$lib/components/learning-unit/LearningTaskCard.svelte";
  import WorkspaceOutline from "$lib/components/ui/WorkspaceOutline.svelte";
  import StatusMessage from "$lib/components/ui/StatusMessage.svelte";
  import { renderMarkdown } from "$lib/utils/markdown";
  import type { ContentGroup, LearnerMaterialContextModule, LearningContentItem } from "$lib/learning-unit/workspace";
  import type { LearningMaterial, LearningSubmission, LearningTask } from "$lib/types/learning";
  import type { SubmitFunction } from "@sveltejs/kit";

  type HistoryState = "not_loaded" | "loading" | "loaded" | "failed" | "unavailable";
  type UploadTaskKind = Extract<LearningTask["kind"], "native" | "visual" | "scratch" | "calliope" | "filius">;
  type ReaderReference = {
    key: string;
    kind: "material" | "submission";
    id: string;
    moduleId: string | null;
    taskId: string | null;
  };

  let {
    learnerSub = null,
    courseId,
    unitTitle = null,
    unitType,
    contentGroups,
    mode,
    activeTaskKey = null,
    activeEditorMode = null,
    workStatus = "editing",
    compactSurface = "task",
    navigationVisible = true,
    collapsedItemKeys = [],
    contextModules = [],
    expandedModuleMaterialKeys = {},
    expandedContextModuleIds = [],
    expandedSubmissionModuleIds = [],
    expandedSubmissionKeys = [],
    focusedContextModuleId = null,
    closedContextModuleTitle = null,
    readingReferenceKey = null,
    contextScrollTop = 0,
    workScrollTop = 0,
    readerScrollTop = 0,
    historyByTask,
    historyStateByTask = {},
    submittedTaskId = null,
    submissionMessage = null,
    submissionErrorTaskId = null,
    submissionErrorMessage = null,
    feedbackPendingTaskId = null,
    feedbackStatusTaskId = null,
    feedbackStatusMessage = null,
    pendingSubmissionIntent = null,
    enhanceTaskForm = null,
    onSubmitUploadFeedback = null,
    onBeginTask,
    onPauseTask,
    onCloseModule,
    onSetCompactSurface,
    onToggleMaterial,
    onToggleContextModuleMaterial = null,
    onToggleContextModule = null,
    onToggleContextSubmissions = null,
    onToggleContextSubmission = null,
    onOpenContextReference = null,
    onCloseContextReader = null,
    onUndoCloseModule = null,
    onContextScroll = null,
    onWorkScroll = null,
    onReaderScroll = null,
    onToggleReviewPanel = null,
    onDismissFeedbackStatus = null,
    onProgressPersisted = null
  }: {
    learnerSub?: string | null;
    courseId: string;
    unitTitle?: string | null;
    unitType: "linear" | "modular";
    contentGroups: ContentGroup[];
    mode: "orienting" | "working";
    activeTaskKey?: string | null;
    activeEditorMode?: "text" | "upload" | null;
    workStatus?: "editing" | "result";
    compactSurface?: "task" | "materials";
    navigationVisible?: boolean;
    collapsedItemKeys?: string[];
    contextModules?: LearnerMaterialContextModule[];
    expandedModuleMaterialKeys?: Record<string, string[]>;
    expandedContextModuleIds?: string[];
    expandedSubmissionModuleIds?: string[];
    expandedSubmissionKeys?: string[];
    focusedContextModuleId?: string | null;
    closedContextModuleTitle?: string | null;
    readingReferenceKey?: string | null;
    contextScrollTop?: number;
    workScrollTop?: number;
    readerScrollTop?: number;
    historyByTask: Record<string, LearningSubmission[]>;
    historyStateByTask?: Record<string, HistoryState>;
    submittedTaskId?: string | null;
    submissionMessage?: string | null;
    submissionErrorTaskId?: string | null;
    submissionErrorMessage?: string | null;
    feedbackPendingTaskId?: string | null;
    feedbackStatusTaskId?: string | null;
    feedbackStatusMessage?: string | null;
    pendingSubmissionIntent?: "feedback" | "submit" | null;
    enhanceTaskForm?: ((taskId: string) => SubmitFunction | undefined) | null;
    onSubmitUploadFeedback?: ((payload: {
      taskId: string;
      taskKind: UploadTaskKind;
      file: File;
      moduleId: string | null;
    }) => void | Promise<void>) | null;
    onBeginTask: (itemKey: string, mode: "text" | "upload") => void;
    onPauseTask: () => void;
    onCloseModule: (moduleId: string) => void;
    onSetCompactSurface: (surface: "task" | "materials") => void;
    onToggleMaterial: (itemKey: string) => void;
    onToggleContextModuleMaterial?: ((moduleId: string, itemKey: string) => void) | null;
    onToggleContextModule?: ((moduleId: string) => void | Promise<void>) | null;
    onToggleContextSubmissions?: ((moduleId: string) => void | Promise<void>) | null;
    onToggleContextSubmission?: ((referenceKey: string) => void) | null;
    onOpenContextReference?: ((referenceKey: string) => void | Promise<void>) | null;
    onCloseContextReader?: (() => void) | null;
    onUndoCloseModule?: (() => void) | null;
    onContextScroll?: ((scrollTop: number) => void) | null;
    onWorkScroll?: ((scrollTop: number) => void) | null;
    onReaderScroll?: ((scrollTop: number) => void) | null;
    onToggleReviewPanel?: ((taskId: string) => void | Promise<void>) | null;
    onDismissFeedbackStatus?: ((taskId: string) => void) | null;
    onProgressPersisted?: (() => void | Promise<void>) | null;
  } = $props();

  let contextScrollSurface = $state<HTMLDivElement | null>(null);
  let workScrollSurface = $state<HTMLElement | null>(null);
  let readerScrollSurface = $state<HTMLElement | null>(null);
  let deskSurface = $state<HTMLDivElement | null>(null);
  let focusedReaderKey = $state<string | null>(null);

  $effect(() => {
    if (contextScrollSurface && contextScrollSurface.scrollTop !== contextScrollTop) {
      contextScrollSurface.scrollTop = contextScrollTop;
    }
  });

  $effect(() => {
    if (workScrollSurface && workScrollSurface.scrollTop !== workScrollTop) {
      workScrollSurface.scrollTop = workScrollTop;
    }
  });

  $effect(() => {
    if (readerScrollSurface && readerScrollSurface.scrollTop !== readerScrollTop) {
      readerScrollSurface.scrollTop = readerScrollTop;
    }
  });

  $effect(() => {
    if (readingReferenceKey && focusedReaderKey !== readingReferenceKey) {
      focusedReaderKey = readingReferenceKey;
      void tick().then(() => document.getElementById("learner-reference-reader-heading")?.focus({ preventScroll: true }));
    } else if (!readingReferenceKey) {
      focusedReaderKey = null;
    }
  });

  $effect(() => {
    if (!deskSurface) return;
    if (readingReferenceKey) {
      deskSurface.setAttribute("inert", "");
    } else {
      deskSurface.removeAttribute("inert");
    }
  });

  function allItems(): LearningContentItem[] {
    return contentGroups.flatMap((group) => group.items);
  }

  function activeTaskItem(): LearningContentItem | null {
    return allItems().find((item) => item.key === activeTaskKey && item.kind === "task") ?? null;
  }

  function groupForItem(item: LearningContentItem | null): ContentGroup | null {
    if (!item) return null;
    return contentGroups.find((group) => group.items.some((candidate) => candidate.key === item.key)) ?? null;
  }

  function uploadOnly(task: LearningTask): boolean {
    return task.kind === "visual" || task.kind === "scratch" || task.kind === "calliope" || task.kind === "filius";
  }

  function preferredMode(task: LearningTask): "text" | "upload" {
    return uploadOnly(task) ? "upload" : "text";
  }

  function taskKindLabel(task: LearningTask): string {
    if (task.kind === "dialog") return "KI-Dialog";
    if (task.kind === "h5p") return "Interaktive Aufgabe";
    if (uploadOnly(task)) return "Dateiaufgabe";
    return "Textantwort";
  }

  function moduleMeta(group: ContentGroup): string {
    const materials = group.items.filter((item) => item.kind === "material").length;
    const tasks = group.items.filter((item) => item.kind === "task").length;
    return `${materials} ${materials === 1 ? "Material" : "Materialien"} · ${tasks} ${tasks === 1 ? "Aufgabe" : "Aufgaben"}`;
  }

  function taskHistory(taskId: string): LearningSubmission[] {
    return historyByTask[taskId] ?? [];
  }

  function referenceByKey(referenceKey: string | null): ReaderReference | null {
    if (!referenceKey) return null;
    for (const item of contextModules.flatMap((module) => module.items)) {
      if (item.material && item.key === referenceKey) {
        return {
          key: item.key,
          kind: "material",
          id: item.material.id,
          moduleId: item.moduleId ?? null,
          taskId: null
        };
      }
      if (item.task && `submission:${item.task.id}` === referenceKey) {
        return {
          key: referenceKey,
          kind: "submission",
          id: item.task.id,
          moduleId: item.moduleId ?? null,
          taskId: item.task.id
        };
      }
    }
    return null;
  }

  function materialForReference(reference: ReaderReference | null): LearningMaterial | null {
    if (!reference || reference.kind !== "material") return null;
    return contextModules
      .flatMap((module) => module.items)
      .find((item) => item.material?.id === reference.id)?.material ?? null;
  }

  function taskForReference(reference: ReaderReference | null): LearningContentItem | null {
    if (!reference?.taskId) return null;
    return contextModules
      .flatMap((module) => module.items)
      .find((item) => item.task?.id === reference.taskId) ?? null;
  }

  const readerReference = $derived.by(() => referenceByKey(readingReferenceKey));
  const readerMaterial = $derived.by(() => materialForReference(readerReference));
  const readerTaskItem = $derived.by(() => taskForReference(readerReference));
  const activeItem = $derived.by(() => activeTaskItem());

  function safeReferenceKey(referenceKey: string): string {
    return referenceKey.replace(/[^a-zA-Z0-9_-]+/g, "-");
  }

  async function closeReader(): Promise<void> {
    const referenceKey = readingReferenceKey;
    onCloseContextReader?.();
    await tick();
    if (referenceKey) {
      document.getElementById(`reference-reader-trigger-${safeReferenceKey(referenceKey)}`)?.focus();
    }
  }
</script>

<div class:learner-surface--inactive={mode !== "orienting"} aria-hidden={mode !== "orienting"}>
  <section class="learner-orientation" aria-label="Orientieren">
    {#if navigationVisible}
      <WorkspaceOutline
        title="Inhaltsverzeichnis"
        groups={contentGroups.map((group) => ({
          id: group.id,
          title: group.title,
          items: group.items.map((item) => ({ key: item.key, title: item.title }))
        }))}
        activeItemKeys={[]}
        onOpenItem={(itemKey) => document.getElementById(`orientation-${itemKey}`)?.scrollIntoView({ behavior: "smooth", block: "start" })}
      />
    {/if}

    <div class="learner-orientation__content">
      {#if unitTitle}
        <header class="learner-orientation__header">
          <p class="workspace-label">Lerneinheit</p>
          <h1>{unitTitle}</h1>
        </header>
      {/if}
      {#each contentGroups as group, index}
        <section class="learner-orientation__module" aria-label={group.title ?? `Modul ${index + 1}`}>
          <header class="learner-orientation__module-header">
            <div>
              <p class="workspace-label">{unitType === "modular" ? `Modul ${index + 1}` : "Abschnitt"}</p>
              <h3>{group.title ?? `Abschnitt ${index + 1}`}</h3>
              <p class="learner-orientation__module-meta">{moduleMeta(group)}</p>
            </div>
            {#if unitType === "modular"}
              <button
                class="workspace-top-action workspace-top-action--quiet workspace-top-action--subtle"
                type="button"
                aria-label="Modul schließen"
                onclick={() => onCloseModule(group.id)}
              >
                Schließen
              </button>
            {/if}
          </header>

          {#if group.items.some((item) => item.kind === "material")}
            <div class="learner-orientation__materials" aria-label="Materialien">
              {#each group.items.filter((item) => item.kind === "material") as item}
                {#if item.material}
                  <LearningMaterialCard
                    material={item.material}
                    domId={`orientation-${item.key}`}
                    contextLabel={null}
                    expanded={!collapsedItemKeys.includes(item.key)}
                    onToggle={() => onToggleMaterial(item.key)}
                  />
                {/if}
              {/each}
            </div>
          {/if}

          <div class="learner-orientation__tasks" aria-label="Aufgaben">
            {#each group.items.filter((item) => item.kind === "task") as item}
              {#if item.task}
                {@const task = item.task}
                <LearningTaskCard
                  {learnerSub}
                  {courseId}
                  {task}
                  taskTitle={item.title}
                  contextLabel={null}
                  {unitType}
                  moduleId={item.moduleId ?? null}
                  history={taskHistory(task.id)}
                  historyState={historyStateByTask[task.id] ?? "not_loaded"}
                  domId={`task-row-${task.id}`}
                  expanded={true}
                  compactLayout={true}
                  submitted={submittedTaskId === task.id}
                  message={submissionMessage}
                  errorMessage={submissionErrorTaskId === task.id ? submissionErrorMessage : null}
                  feedbackPending={feedbackPendingTaskId === task.id}
                  feedbackStatusMessage={mode === "orienting" && feedbackStatusTaskId === task.id
                    ? feedbackStatusMessage
                    : null}
                  pendingIntent={feedbackPendingTaskId === task.id ? pendingSubmissionIntent : null}
                  submissionFocused={false}
                  reviewPanelOpen={false}
                  enhanceSubmit={enhanceTaskForm?.(task.id)}
                  onToggleReviewPanel={() => onToggleReviewPanel?.(task.id)}
                  onDismissFeedbackStatus={() => onDismissFeedbackStatus?.(task.id)}
                  onEnterSubmissionWorkspace={() => onBeginTask(item.key, "text")}
                  onEnterUploadWorkspace={() => onBeginTask(item.key, preferredMode(task))}
                  {onProgressPersisted}
                />
              {/if}
            {/each}
          </div>
        </section>
      {/each}
    </div>
  </section>
 </div>

<div class:learner-surface--inactive={mode !== "working"} aria-hidden={mode !== "working"}>
  {#if activeItem?.task}
    {@const task = activeItem.task}
    <div class="learner-task-workbench-container">
      <header class="learner-task-header">
        <button id="learner-task-back" class="learner-task-header__back" type="button" onclick={onPauseTask}>
          ← Zurück zu Modul {groupForItem(activeItem)?.title ?? "Inhalte"}
        </button>
        <div class="learner-task-header__identity">
          <strong>{activeItem.title}</strong>
          <span>{workStatus === "result" ? "Ergebnis" : "In Bearbeitung"}</span>
        </div>
      </header>
      <section
        class:learner-task-workbench--dialog={task.kind === "dialog"}
        class="learner-task-workbench"
        data-compact-surface={compactSurface}
        data-reader-active={readerReference ? "true" : "false"}
        aria-label="Aufgabe bearbeiten"
      >
      {#if readerReference}
        <section
          bind:this={readerScrollSurface}
          class="learner-context-reader__scroll"
          aria-label="Dokument groß lesen"
          onscroll={(event) => onReaderScroll?.(event.currentTarget.scrollTop)}
        >
          <nav class="learner-context-reader__toolbar" aria-label="Lesemodus">
            <button
              class="learner-context-reader__back"
              type="button"
              aria-label="Zurück zur Aufgabe"
              onclick={closeReader}
            >
              ← Zurück zur Aufgabe
            </button>
          </nav>
          <LearningReferenceDocument
            referenceKey={readerReference.key}
            label={readerReference.kind === "material" ? "Material" : "Eigene frühere Abgabe"}
            title={readerMaterial?.title ?? readerTaskItem?.title ?? readerReference.id}
            material={readerMaterial}
            submissions={readerReference.taskId ? taskHistory(readerReference.taskId) : []}
            {courseId}
            taskId={readerReference.taskId}
            expanded={true}
            readerMode={true}
          />
        </section>
      {/if}
      <div
        bind:this={deskSurface}
        class="learner-task-workbench__desk"
        aria-hidden={readerReference ? "true" : undefined}
      >
      {#if task.kind !== "dialog"}
      <nav class="learner-task-workbench__switch" aria-label="Arbeitsbereich wählen">
        <button
          class:learner-task-workbench__switch-button--active={compactSurface === "task"}
          class="learner-task-workbench__switch-button"
          type="button"
          aria-pressed={compactSurface === "task"}
          onclick={() => onSetCompactSurface("task")}
        >Aufgabe</button>
        <button
          class:learner-task-workbench__switch-button--active={compactSurface === "materials"}
          class="learner-task-workbench__switch-button"
          type="button"
          aria-pressed={compactSurface === "materials"}
          onclick={() => onSetCompactSurface("materials")}
        >Materialien</button>
      </nav>

      <aside class="learner-task-context" data-work-surface="materials" aria-label="Aufgabe und Kontext">
        <div
          bind:this={contextScrollSurface}
          class="learner-task-context__scroll"
          onscroll={(event) => onContextScroll?.(event.currentTarget.scrollTop)}
        >
            <header class="learner-task-context__header">
              <p class="workspace-label">{activeItem.title} · {taskKindLabel(task)}</p>
              <div class="learner-task-context__instruction">
                {@html renderMarkdown(task.instruction_md)}
              </div>
            </header>

            <LearnerMaterialContext
              {courseId}
              modules={contextModules}
              expandedModuleIds={expandedContextModuleIds}
              {expandedModuleMaterialKeys}
              {expandedSubmissionModuleIds}
              {expandedSubmissionKeys}
              {historyByTask}
              {historyStateByTask}
              focusedModuleId={focusedContextModuleId}
              closedModuleTitle={closedContextModuleTitle}
              onToggleModule={onToggleContextModule}
              onToggleMaterial={onToggleContextModuleMaterial}
              onToggleSubmissionGroup={onToggleContextSubmissions}
              onToggleSubmission={onToggleContextSubmission}
              onOpenReference={onOpenContextReference}
              onCloseModule={onCloseModule}
              {onUndoCloseModule}
            />
        </div>

      </aside>
      {/if}

      <main
        bind:this={workScrollSurface}
        class="learner-task-workbench__main"
        data-work-surface="task"
        aria-label="Bearbeitung"
        onscroll={(event) => onWorkScroll?.(event.currentTarget.scrollTop)}
      >
        <LearningTaskCard
          {learnerSub}
          {courseId}
          {task}
          taskTitle={activeItem.title}
          contextLabel={null}
          {unitType}
          moduleId={activeItem.moduleId ?? null}
          history={taskHistory(task.id)}
          historyState={historyStateByTask[task.id] ?? "not_loaded"}
          domId={`task-workspace-${task.id}`}
          expanded={true}
          compactLayout={true}
          workspaceOnly={true}
          dialogCompactSurface={compactSurface}
          dialogExpandedModuleMaterialKeys={expandedModuleMaterialKeys}
          dialogExpandedContextModuleIds={expandedContextModuleIds}
          dialogExpandedSubmissionModuleIds={expandedSubmissionModuleIds}
          dialogExpandedSubmissionKeys={expandedSubmissionKeys}
          dialogContextModules={contextModules}
          dialogHistoryByTask={historyByTask}
          dialogHistoryStateByTask={historyStateByTask}
          dialogFocusedContextModuleId={focusedContextModuleId}
          dialogClosedContextModuleTitle={closedContextModuleTitle}
          submitted={submittedTaskId === task.id}
          message={submissionMessage}
          errorMessage={submissionErrorTaskId === task.id ? submissionErrorMessage : null}
          feedbackPending={feedbackPendingTaskId === task.id}
          feedbackStatusMessage={feedbackStatusTaskId === task.id ? feedbackStatusMessage : null}
          pendingIntent={feedbackPendingTaskId === task.id ? pendingSubmissionIntent : null}
          submissionFocused={workStatus === "editing"}
          initialSubmissionMode={activeEditorMode}
          reviewPanelOpen={workStatus === "result"}
          enhanceSubmit={enhanceTaskForm?.(task.id)}
          onExitSubmissionWorkspace={null}
          hideDialogPauseAction={true}
          onSetDialogCompactSurface={onSetCompactSurface}
          onOpenDialogContext={onOpenContextReference}
          onToggleDialogMaterial={onToggleContextModuleMaterial}
          onToggleDialogContextModule={onToggleContextModule}
          onToggleDialogSubmissionGroup={onToggleContextSubmissions}
          onToggleDialogSubmission={onToggleContextSubmission}
          onCloseDialogContextModule={onCloseModule}
          onUndoCloseDialogContextModule={onUndoCloseModule}
          onToggleReviewPanel={() => onToggleReviewPanel?.(task.id)}
          onDismissFeedbackStatus={() => onDismissFeedbackStatus?.(task.id)}
          onSubmitUploadFeedback={onSubmitUploadFeedback}
          {onProgressPersisted}
        />
      </main>
      </div>
      </section>
    </div>
  {:else}
    <section class="learning-unit-empty-state" aria-label="Aufgabe nicht verfügbar">
      <StatusMessage tone="error" title="Aufgabe nicht verfügbar" description="Diese Aufgabe ist nicht mehr verfügbar." />
      <button class="workspace-top-action workspace-top-action--quiet" type="button" onclick={onPauseTask}>Zurück zu den Inhalten</button>
    </section>
  {/if}
</div>
