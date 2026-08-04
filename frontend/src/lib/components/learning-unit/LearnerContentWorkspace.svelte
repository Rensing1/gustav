<script lang="ts">
  import LearningMaterialCard from "$lib/components/learning-unit/LearningMaterialCard.svelte";
  import LearningReferenceDocument from "$lib/components/learning-unit/LearningReferenceDocument.svelte";
  import LearningTaskCard from "$lib/components/learning-unit/LearningTaskCard.svelte";
  import WorkspaceOutline from "$lib/components/ui/WorkspaceOutline.svelte";
  import { renderMarkdown } from "$lib/utils/markdown";
  import type { LearnerContextReference } from "$lib/learning-unit/learner-workspace-state";
  import type { ContentGroup, LearningContentItem } from "$lib/learning-unit/workspace";
  import type { LearningMaterial, LearningSubmission, LearningTask } from "$lib/types/learning";
  import type { SubmitFunction } from "@sveltejs/kit";

  type HistoryState = "not_loaded" | "loading" | "loaded" | "failed" | "unavailable";
  type UploadTaskKind = Extract<LearningTask["kind"], "native" | "visual" | "scratch" | "calliope" | "filius">;

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
    manualContextReferences = [],
    contextPickerOpen = false,
    expandedContextModuleIds = [],
    expandedReferenceKeys = [],
    readingReferenceKey = null,
    contextScrollTop = 0,
    workScrollTop = 0,
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
    onToggleContextPicker = null,
    onToggleContextModule = null,
    onAddContextReference = null,
    onRemoveContextReference = null,
    onToggleContextReference = null,
    onOpenContextReference = null,
    onCloseContextReader = null,
    onContextScroll = null,
    onWorkScroll = null,
    onToggleReviewPanel = null,
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
    contextModules?: Array<{
      id: string;
      title: string;
      current: boolean;
      opened?: boolean;
      loaded: boolean;
      loading: boolean;
      error: string | null;
      items: LearningContentItem[];
    }>;
    manualContextReferences?: LearnerContextReference[];
    contextPickerOpen?: boolean;
    expandedContextModuleIds?: string[];
    expandedReferenceKeys?: string[];
    readingReferenceKey?: string | null;
    contextScrollTop?: number;
    workScrollTop?: number;
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
    onToggleContextPicker?: (() => void) | null;
    onToggleContextModule?: ((moduleId: string) => void | Promise<void>) | null;
    onAddContextReference?: ((reference: LearnerContextReference) => void) | null;
    onRemoveContextReference?: ((referenceKey: string) => void) | null;
    onToggleContextReference?: ((referenceKey: string) => void | Promise<void>) | null;
    onOpenContextReference?: ((referenceKey: string) => void | Promise<void>) | null;
    onCloseContextReader?: (() => void) | null;
    onContextScroll?: ((scrollTop: number) => void) | null;
    onWorkScroll?: ((scrollTop: number) => void) | null;
    onToggleReviewPanel?: ((taskId: string) => void | Promise<void>) | null;
    onProgressPersisted?: (() => void | Promise<void>) | null;
  } = $props();

  let contextScrollSurface = $state<HTMLDivElement | null>(null);
  let workScrollSurface = $state<HTMLElement | null>(null);

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

  function currentMaterials(item: LearningContentItem | null): LearningContentItem[] {
    return groupForItem(item)?.items.filter((candidate) => candidate.kind === "material") ?? [];
  }

  function currentMaterialRecords(item: LearningContentItem | null): LearningMaterial[] {
    return currentMaterials(item)
      .map((entry) => entry.material)
      .filter((material): material is LearningMaterial => Boolean(material));
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

  function referenceByKey(referenceKey: string | null): LearnerContextReference | null {
    if (!referenceKey) return null;
    const manual = manualContextReferences.find((reference) => reference.key === referenceKey);
    if (manual) return manual;
    const material = contextModules
      .flatMap((module) => module.items)
      .find((item) => item.key === referenceKey && item.material);
    if (material?.material) {
      return {
        key: material.key,
        kind: "material",
        id: material.material.id,
        moduleId: material.moduleId ?? null,
        taskId: null
      };
    }
    return null;
  }

  function materialForReference(reference: LearnerContextReference | null): LearningMaterial | null {
    if (!reference || reference.kind !== "material") return null;
    return (
      contextModules
        .flatMap((module) => module.items)
        .find((item) => item.material?.id === reference.id)?.material ?? null
    );
  }

  function taskForReference(reference: LearnerContextReference | null): LearningContentItem | null {
    if (!reference?.taskId) return null;
    return (
      contextModules
        .flatMap((module) => module.items)
        .find((item) => item.task?.id === reference.taskId) ?? null
    );
  }

  function referenceAlreadyAdded(key: string): boolean {
    return currentMaterials(activeItem).some((item) => item.key === key)
      || manualContextReferences.some((reference) => reference.key === key);
  }

  function contextReferenceDocuments(item: LearningContentItem | null) {
    const documents: Array<{
      key: string;
      label: string;
      title: string;
      material: LearningMaterial | null;
      submissions: LearningSubmission[];
      current: boolean;
    }> = [];
    const seen = new Set<string>();

    for (const materialItem of currentMaterials(item)) {
      if (!materialItem.material || seen.has(materialItem.key)) continue;
      seen.add(materialItem.key);
      documents.push({
        key: materialItem.key,
        label: "Material · Aktuelles Modul",
        title: materialItem.title,
        material: materialItem.material,
        submissions: [],
        current: true
      });
    }

    for (const reference of manualContextReferences) {
      if (seen.has(reference.key)) continue;
      seen.add(reference.key);
      const material = materialForReference(reference);
      const taskItem = taskForReference(reference);
      documents.push({
        key: reference.key,
        label: reference.kind === "material" ? "Angeheftetes Material" : "Eigene frühere Abgabe",
        title: material?.title ?? taskItem?.title ?? reference.id,
        material,
        submissions: reference.taskId ? taskHistory(reference.taskId) : [],
        current: false
      });
    }

    return documents;
  }

  function dialogContextEntries(item: LearningContentItem | null) {
    const entries: Array<{
      key: string;
      kind: "material" | "submission";
      label: string;
      title: string;
      bodyMd: string | null;
      meta: string | null;
      fileUrl?: string | null;
    }> = [];
    const seen = new Set<string>();

    for (const materialItem of currentMaterials(item)) {
      if (!materialItem.material || seen.has(materialItem.key)) continue;
      seen.add(materialItem.key);
      entries.push({
        key: materialItem.key,
        kind: "material",
        label: "Material",
        title: materialItem.title,
        bodyMd: materialItem.material.body_md ?? null,
        meta: "Aktueller Abschnitt",
        fileUrl: materialItem.material.file_url ?? null
      });
    }

    for (const reference of manualContextReferences) {
      if (seen.has(reference.key)) continue;
      const material = materialForReference(reference);
      const taskItem = taskForReference(reference);
      if (material) {
        seen.add(reference.key);
        entries.push({
          key: reference.key,
          kind: "material",
          label: "Material",
          title: material.title,
          bodyMd: material.body_md ?? null,
          meta: "Angeheftet",
          fileUrl: material.file_url ?? null
        });
      } else if (reference.kind === "submission" && reference.taskId) {
        const submission = taskHistory(reference.taskId)[0] ?? null;
        seen.add(reference.key);
        entries.push({
          key: reference.key,
          kind: "submission",
          label: "Eigene frühere Abgabe",
          title: taskItem?.title ?? "Frühere Abgabe",
          bodyMd: submission?.text_body ?? submission?.feedback_md ?? null,
          meta: submission ? `Versuch ${submission.attempt_nr}` : "Wird geladen"
        });
      }
    }

    return entries;
  }

  function dialogContextModuleOptions() {
    return contextModules.map((contextModule) => {
      const options: Array<{
        key: string;
        kind: "material" | "submission";
        id: string;
        moduleId: string | null;
        taskId: string | null;
        title: string;
        added: boolean;
      }> = [];
      for (const option of contextModule.items) {
        if (option.material) {
          options.push({
            key: option.key,
            kind: "material",
            id: option.material.id,
            moduleId: option.moduleId ?? contextModule.id,
            taskId: null,
            title: option.title,
            added: referenceAlreadyAdded(option.key)
          });
        }
        if (!option.material && option.task?.has_submission) {
          const key = `submission:${option.task.id}`;
          options.push({
            key,
            kind: "submission",
            id: option.task.id,
            moduleId: option.moduleId ?? contextModule.id,
            taskId: option.task.id,
            title: option.title,
            added: referenceAlreadyAdded(key)
          });
        }
      }
      return {
        id: contextModule.id,
        title: contextModule.title,
        current: contextModule.current,
        loaded: contextModule.loaded,
        loading: contextModule.loading,
        error: contextModule.error,
        options
      };
    });
  }

  const readerReference = $derived.by(() => referenceByKey(readingReferenceKey));
  const readerMaterial = $derived.by(() => materialForReference(readerReference));
  const readerTaskItem = $derived.by(() => taskForReference(readerReference));
  const activeItem = $derived.by(() => activeTaskItem());
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
                  feedbackStatusMessage={feedbackStatusTaskId === task.id ? feedbackStatusMessage : null}
                  pendingIntent={feedbackPendingTaskId === task.id ? pendingSubmissionIntent : null}
                  submissionFocused={false}
                  reviewPanelOpen={false}
                  enhanceSubmit={enhanceTaskForm?.(task.id)}
                  onToggleReviewPanel={() => onToggleReviewPanel?.(task.id)}
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
        aria-label="Aufgabe bearbeiten"
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
          {#if readerReference}
            <article class="learner-context-reader" aria-label="Kontext lesen">
              <header class="learner-context-reader__header">
                <button class="learner-context-reader__back" type="button" onclick={() => onCloseContextReader?.()}>
                  ← Zur Kontextliste
                </button>
                <p class="workspace-label">
                  {readerReference.kind === "material" ? "Material" : "Eigene frühere Abgabe"}
                </p>
                <h2>{readerMaterial?.title ?? readerTaskItem?.title ?? "Kontext"}</h2>
              </header>

              {#if readerMaterial?.kind === "markdown" && readerMaterial.body_md}
                <div class="learner-context-reader__body">{@html renderMarkdown(readerMaterial.body_md)}</div>
              {:else if readerMaterial}
                <div class="learner-context-reader__file">
                  <p>{readerMaterial.filename_original ?? "Dateimaterial"}</p>
                  {#if readerMaterial.file_url}
                    <a href={readerMaterial.file_url} target="_blank" rel="noreferrer">Material öffnen</a>
                  {/if}
                </div>
              {:else if readerReference.kind === "submission" && readerReference.taskId}
                {@const submission = taskHistory(readerReference.taskId)[0] ?? null}
                {#if submission}
                  <div class="learner-context-reader__submission">
                    <p class="learner-context-reader__meta">
                      Eigene Abgabe · Versuch {submission.attempt_nr} · {new Date(submission.created_at).toLocaleDateString("de-DE")}
                    </p>
                    {#if submission.text_body}
                      <div class="learner-context-reader__body">{@html renderMarkdown(submission.text_body)}</div>
                    {/if}
                    {#if submission.feedback_md}
                      <details class="learner-context-reader__response">
                        <summary>Rückmeldung</summary>
                        <div class="learner-context-reader__body">{@html renderMarkdown(submission.feedback_md)}</div>
                      </details>
                    {/if}
                    {#if submission.analysis_json?.criteria_results?.length}
                      <details class="learner-context-reader__response">
                        <summary>Auswertung</summary>
                        {#each submission.analysis_json.criteria_results as result}
                          <section class="learner-context-reader__criterion">
                            <strong>{result.criterion}</strong>
                            {#if result.explanation_md}
                              <div class="learner-context-reader__body">{@html renderMarkdown(result.explanation_md)}</div>
                            {/if}
                          </section>
                        {/each}
                      </details>
                    {/if}
                  </div>
                {:else}
                  <p class="workspace-note">Die frühere Abgabe wird geladen …</p>
                {/if}
              {/if}
            </article>
          {:else}
            <header class="learner-task-context__header">
              <p class="workspace-label">{activeItem.title} · {taskKindLabel(task)}</p>
              <div class="learner-task-context__instruction">
                {@html renderMarkdown(task.instruction_md)}
              </div>
            </header>

            <section class="learner-task-context__materials" aria-labelledby="learner-context-materials-title">
              <h3 id="learner-context-materials-title">Materialien</h3>
              {#if contextReferenceDocuments(activeItem).length}
                <div class="learner-task-context__list" aria-label="Quellenstapel">
                  {#each contextReferenceDocuments(activeItem) as document (document.key)}
                    <div class="learner-task-context__document-row">
                      <LearningReferenceDocument
                        referenceKey={document.key}
                        label={document.label}
                        title={document.title}
                        material={document.material}
                        submissions={document.submissions}
                        expanded={document.current
                          ? !collapsedItemKeys.includes(document.key)
                          : expandedReferenceKeys.includes(document.key)}
                        onToggle={(referenceKey) => document.current
                          ? onToggleMaterial(referenceKey)
                          : onToggleContextReference?.(referenceKey)}
                        onOpenReader={onOpenContextReference}
                      />
                      {#if !document.current}
                        <button
                          class="learner-task-context__remove"
                          type="button"
                          aria-label={`${document.title} aus dem Kontext entfernen`}
                          onclick={() => onRemoveContextReference?.(document.key)}
                        >Entfernen</button>
                      {/if}
                    </div>
                  {/each}
                </div>
              {:else}
                <p class="workspace-note">Für diesen Abschnitt sind keine Materialien hinterlegt.</p>
              {/if}

              {#if contextModules.some((module) => module.opened && !module.current)}
                <div class="learner-task-context__opened" aria-label="Materialien aus geöffneten Modulen">
                  <p class="workspace-label">Weitere geöffnete Module</p>
                  {#each contextModules.filter((module) => module.opened && !module.current) as contextModule}
                    <section class="learner-task-context__opened-module">
                      <button
                        class="learner-context-picker__module-toggle"
                        type="button"
                        aria-expanded={expandedContextModuleIds.includes(contextModule.id)}
                        onclick={() => onToggleContextModule?.(contextModule.id)}
                      >
                        <span>Geöffnetes Modul</span>
                        <strong>{contextModule.title}</strong>
                      </button>
                      {#if expandedContextModuleIds.includes(contextModule.id)}
                        <div class="learner-context-picker__module-body">
                          {#each contextModule.items.filter((item) => item.material) as materialItem}
                            <button class="learner-task-context__item" type="button" onclick={() => onOpenContextReference?.(materialItem.key)}>
                              <span class="learner-task-context__item-type">Material</span>
                              <strong>{materialItem.title}</strong>
                            </button>
                          {/each}
                        </div>
                      {/if}
                    </section>
                  {/each}
                </div>
              {/if}

              <button class="learner-task-context__add" type="button" aria-expanded={contextPickerOpen} onclick={() => onToggleContextPicker?.()}>
                + Kontext hinzufügen
              </button>

              {#if contextPickerOpen}
                <section class="learner-context-picker" aria-label="Kontext auswählen">
                  {#each contextModules as contextModule}
                    <div class="learner-context-picker__module">
                      <button
                        class="learner-context-picker__module-toggle"
                        type="button"
                        aria-expanded={expandedContextModuleIds.includes(contextModule.id)}
                        onclick={() => onToggleContextModule?.(contextModule.id)}
                      >
                        <span>{contextModule.current ? "Aktuelles Modul" : "Weiteres Modul"}</span>
                        <strong>{contextModule.title}</strong>
                      </button>
                      {#if expandedContextModuleIds.includes(contextModule.id)}
                        <div class="learner-context-picker__module-body">
                          {#if contextModule.loading}
                            <p class="workspace-note">Inhalte werden geladen …</p>
                          {:else if contextModule.error}
                            <p class="workspace-note workspace-note--error">{contextModule.error}</p>
                          {:else if contextModule.loaded}
                            {#each contextModule.items as option}
                              {#if option.material}
                                {@const key = option.key}
                                <button
                                  class="learner-context-picker__add-item"
                                  type="button"
                                  disabled={referenceAlreadyAdded(key)}
                                  onclick={() => onAddContextReference?.({
                                    key,
                                    kind: "material",
                                    id: option.material?.id ?? "",
                                    moduleId: option.moduleId ?? contextModule.id,
                                    taskId: null
                                  })}
                                >
                                  <span>Material</span><strong>{option.title}</strong>
                                </button>
                              {:else if option.task?.has_submission}
                                {@const submissionKey = `submission:${option.task.id}`}
                                <button
                                  class="learner-context-picker__add-item"
                                  type="button"
                                  disabled={referenceAlreadyAdded(submissionKey)}
                                  onclick={() => onAddContextReference?.({
                                    key: submissionKey,
                                    kind: "submission",
                                    id: option.task?.id ?? "",
                                    moduleId: option.moduleId ?? contextModule.id,
                                    taskId: option.task?.id ?? null
                                  })}
                                >
                                  <span>Eigene frühere Abgabe</span><strong>{option.title}</strong>
                                </button>
                              {/if}
                            {/each}
                          {/if}
                        </div>
                      {/if}
                    </div>
                  {/each}
                </section>
              {/if}
            </section>
          {/if}
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
          dialogContextMaterials={currentMaterialRecords(activeItem)}
          dialogContextEntries={dialogContextEntries(activeItem)}
          dialogReadingContextKey={readingReferenceKey}
          dialogContextPickerOpen={contextPickerOpen}
          dialogExpandedContextModuleIds={expandedContextModuleIds}
          dialogContextModules={dialogContextModuleOptions()}
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
          onCloseDialogContext={onCloseContextReader}
          onToggleDialogContextPicker={onToggleContextPicker}
          onToggleDialogContextModule={onToggleContextModule}
          onAddDialogContextReference={onAddContextReference}
          onToggleReviewPanel={() => onToggleReviewPanel?.(task.id)}
          onSubmitUploadFeedback={onSubmitUploadFeedback}
          {onProgressPersisted}
        />
      </main>
      </section>
    </div>
  {:else}
    <section class="learning-unit-empty-state" aria-label="Aufgabe nicht verfügbar">
      <p class="workspace-note workspace-note--error">Diese Aufgabe ist nicht mehr verfügbar.</p>
      <button class="workspace-top-action workspace-top-action--quiet" type="button" onclick={onPauseTask}>Zurück zu den Inhalten</button>
    </section>
  {/if}
</div>
