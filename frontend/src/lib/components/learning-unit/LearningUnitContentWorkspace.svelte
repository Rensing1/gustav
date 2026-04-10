<script lang="ts">
  import LearningMaterialCard from "$lib/components/learning-unit/LearningMaterialCard.svelte";
  import LearningTaskCard from "$lib/components/learning-unit/LearningTaskCard.svelte";
  import WorkspaceFrameHeader from "$lib/components/ui/WorkspaceFrameHeader.svelte";
  import WorkspaceOutline from "$lib/components/ui/WorkspaceOutline.svelte";
  import WorkspaceSettingsMenu from "$lib/components/ui/WorkspaceSettingsMenu.svelte";
  import type { SubmitFunction } from "@sveltejs/kit";
  import type {
    ContentGroup,
    LearningContentItem,
    PaneId
  } from "$lib/learning-unit/workspace";
  import type { LearningSubmission } from "$lib/types/learning";

  let {
    titleLabel,
    title,
    meta = null,
    courseId,
    unitType,
    moduleId = null,
    tocOpen,
    splitView,
    activePane,
    visiblePaneIds,
    contentGroups,
    paneItems,
    historyByTask,
    submittedTaskId = null,
    submissionMessage = null,
    submissionErrorTaskId = null,
    submissionErrorMessage = null,
    feedbackPendingTaskId = null,
    feedbackStatusTaskId = null,
    feedbackStatusMessage = null,
    pendingSubmissionIntent = null,
    submissionFocusByPane,
    submissionModeByPane,
    reviewFocusByPane = { left: null, right: null },
    enhanceTaskForm = null,
    showSplitToggle = true,
    layoutMenuEnabled = false,
    tocWidth = 16.25,
    workspaceWidth = 112,
    splitRatio = 50,
    tocGap = 1.1,
    paneGap = 1.1,
    fontScale = 1,
    itemDomId,
    onToggleToc,
    onToggleSplitView,
    onResetLayout,
    onUpdateTocWidth,
    onPreviewWorkspaceWidth,
    onCommitWorkspaceWidth,
    onPreviewFontScale,
    onCommitFontScale,
    onUpdateSplitRatio,
    onUpdateTocGap,
    onUpdatePaneGap,
    onSetActivePane,
    onOpenItem,
    onRemoveGroup = undefined,
    onToggleItem,
    onEnterSubmissionWorkspace,
    onEnterUploadWorkspace,
    onExitSubmissionWorkspace,
    onToggleReviewPanel,
    onSubmitUploadFeedback = null
  }: {
    titleLabel: string;
    title: string;
    meta?: string | null;
    courseId: string;
    unitType: "linear" | "modular";
    moduleId?: string | null;
    tocOpen: boolean;
    splitView: boolean;
    activePane: PaneId;
    visiblePaneIds: PaneId[];
    contentGroups: ContentGroup[];
    paneItems: Record<PaneId, Array<{ item: ContentGroup["items"][number]; expanded: boolean }>>;
    historyByTask: Record<string, LearningSubmission[]>;
    submittedTaskId?: string | null;
    submissionMessage?: string | null;
    submissionErrorTaskId?: string | null;
    submissionErrorMessage?: string | null;
    feedbackPendingTaskId?: string | null;
    feedbackStatusTaskId?: string | null;
    feedbackStatusMessage?: string | null;
    pendingSubmissionIntent?: "feedback" | "submit" | null;
    submissionFocusByPane: Record<PaneId, string | null>;
    submissionModeByPane: Record<PaneId, "text" | "upload" | null>;
    reviewFocusByPane?: Record<PaneId, string | null>;
    enhanceTaskForm?: ((taskId: string, paneId: PaneId) => SubmitFunction | undefined) | null;
    showSplitToggle?: boolean;
    layoutMenuEnabled?: boolean;
    tocWidth?: number;
    workspaceWidth?: number;
    splitRatio?: number;
    tocGap?: number;
    paneGap?: number;
    fontScale?: number;
    itemDomId: (paneId: PaneId, itemKey: string) => string;
    onToggleToc: () => void;
    onToggleSplitView: () => void;
    onResetLayout: () => void;
    onUpdateTocWidth: (value: number) => void;
    onPreviewWorkspaceWidth: (value: number) => void;
    onCommitWorkspaceWidth: (value: number) => void;
    onPreviewFontScale: (value: number) => void;
    onCommitFontScale: (value: number) => void;
    onUpdateSplitRatio: (value: number) => void;
    onUpdateTocGap: (value: number) => void;
    onUpdatePaneGap: (value: number) => void;
    onSetActivePane: (paneId: PaneId) => void;
    onOpenItem: (itemKey: string) => void;
    onRemoveGroup?: ((groupId: string) => void) | undefined;
    onToggleItem: (paneId: PaneId, itemKey: string) => void;
    onEnterSubmissionWorkspace: (paneId: PaneId, itemKey: string, mode?: "text" | "upload") => void;
    onEnterUploadWorkspace: (paneId: PaneId, itemKey: string) => void;
    onExitSubmissionWorkspace: (paneId: PaneId) => void;
    onToggleReviewPanel: (paneId: PaneId, taskId: string) => void;
    onSubmitUploadFeedback?:
      | ((payload: {
          taskId: string;
          taskKind: "native" | "visual" | "scratch" | "calliope";
          file: File;
          moduleId: string | null;
          paneId: PaneId;
        }) => void | Promise<void>)
      | null;
  } = $props();

  function tocItemActive(itemKey: string): boolean {
    if (unitType === "modular") {
      return contentGroups.some((group) => group.items.some((item) => item.key === itemKey));
    }

    return visiblePaneIds.some((paneId) =>
      (paneItems[paneId] ?? []).some((entry) => entry.item.key === itemKey && entry.expanded)
    );
  }

  function activateOnPointer(node: HTMLElement, paneId: PaneId) {
    function handlePointerDown() {
      onSetActivePane(paneId);
    }

    node.addEventListener("pointerdown", handlePointerDown);

    return {
      destroy() {
        node.removeEventListener("pointerdown", handlePointerDown);
      }
    };
  }

  let layoutMenuOpen = $state(false);
  const shellStyle = $derived.by(
    () =>
      [
        `--learning-unit-toc-width: ${tocWidth}rem`,
        `--learning-unit-workspace-width: ${workspaceWidth}rem`,
        `--learning-unit-split-left: minmax(0, ${splitRatio}fr)`,
        `--learning-unit-split-right: minmax(0, ${100 - splitRatio}fr)`,
        `--learning-unit-toc-gap: ${tocGap}rem`,
        `--learning-unit-pane-gap: ${paneGap}rem`
      ].join("; ")
  );

  function paneItemEntryMap(
    paneId: PaneId
  ): Map<string, { item: LearningContentItem; expanded: boolean }> {
    return new Map((paneItems[paneId] ?? []).map((entry) => [entry.item.key, entry]));
  }

  function modularGroupsForPane(paneId: PaneId): Array<{
    id: string;
    title: string | null;
    materials: Array<{ item: LearningContentItem; expanded: boolean }>;
    tasks: Array<{ item: LearningContentItem; expanded: boolean }>;
  }> {
    const entriesByKey = paneItemEntryMap(paneId);

    return contentGroups
      .map((group) => {
        const entries = group.items
          .map((item) => entriesByKey.get(item.key) ?? null)
          .filter((entry): entry is { item: LearningContentItem; expanded: boolean } => Boolean(entry));

        return {
          id: group.id,
          title: group.title,
          materials: entries.filter((entry) => entry.item.kind === "material"),
          tasks: entries.filter((entry) => entry.item.kind === "task")
        };
      })
      .filter((group) => group.materials.length > 0 || group.tasks.length > 0);
  }

  function moduleDisplayIndex(groupIndex: number): string {
    return `M${String(groupIndex + 1).padStart(2, "0")}`;
  }

  function moduleMetaText(group: {
    materials: Array<{ item: LearningContentItem; expanded: boolean }>;
    tasks: Array<{ item: LearningContentItem; expanded: boolean }>;
  }): string {
    const parts: string[] = [];

    if (group.materials.length > 0) {
      parts.push(group.materials.length === 1 ? "1 Material" : `${group.materials.length} Materialien`);
    }

    if (group.tasks.length > 0) {
      parts.push(group.tasks.length === 1 ? "1 Aufgabe" : `${group.tasks.length} Aufgaben`);
    }

    return parts.join(" · ");
  }
</script>

<svelte:document
  onclick={(event) => {
    const target = event.target;
    if (!(target instanceof Element) || !target.closest("[data-layout-menu-root]")) {
      layoutMenuOpen = false;
    }
  }}
  onkeydown={(event) => {
    if (event.key === "Escape") {
      layoutMenuOpen = false;
    }
  }}
/>

{#if titleLabel || title || meta || layoutMenuEnabled}
  <WorkspaceFrameHeader eyebrow={titleLabel} title={title} meta={meta}>
    {#snippet actions()}
      {#if layoutMenuEnabled}
        <WorkspaceSettingsMenu
          open={layoutMenuOpen}
          {tocOpen}
          {splitView}
          {showSplitToggle}
          {tocWidth}
          {workspaceWidth}
          {splitRatio}
          {tocGap}
          {paneGap}
          {fontScale}
          onToggleMenu={() => {
            layoutMenuOpen = !layoutMenuOpen;
          }}
          {onToggleToc}
          {onToggleSplitView}
          {onResetLayout}
          {onUpdateTocWidth}
          {onPreviewWorkspaceWidth}
          {onCommitWorkspaceWidth}
          {onPreviewFontScale}
          {onCommitFontScale}
          {onUpdateSplitRatio}
          {onUpdateTocGap}
          {onUpdatePaneGap}
        />
      {/if}
    {/snippet}
  </WorkspaceFrameHeader>
{/if}

<section
  class:learning-unit-content-shell--single={!splitView}
  class:learning-unit-content-shell--toc-closed={!tocOpen}
  class="learning-unit-content-shell"
  style={shellStyle}
>
  {#if tocOpen}
    <WorkspaceOutline
      title="Inhaltsverzeichnis"
      groups={contentGroups.map((group) => ({
        id: group.id,
        title: group.title,
        items: group.items.map((item) => ({ key: item.key, title: item.title }))
      }))}
      activeItemKeys={contentGroups.flatMap((group) =>
        group.items.filter((item) => tocItemActive(item.key)).map((item) => item.key)
      )}
      {onOpenItem}
      onRemoveGroup={unitType === "modular" ? onRemoveGroup : undefined}
    />
  {/if}

  <div
    class:learning-unit-pane-grid--single={!splitView}
    class:learning-unit-pane-grid--split={splitView}
    class="learning-unit-pane-grid"
  >
    {#each visiblePaneIds as paneId}
      <section
        class:learning-unit-pane--active={activePane === paneId}
        class="learning-unit-pane"
        aria-label={splitView ? (paneId === "left" ? "Linkes Arbeitsfeld" : "Rechtes Arbeitsfeld") : "Arbeitsfeld"}
        use:activateOnPointer={paneId}
      >
        <div class="learning-unit-workspace-surface">
          {#if paneItems[paneId]?.length}
            {#if unitType === "modular"}
              <div class="learning-unit-pane__stack learning-unit-pane__stack--modules">
                {#each modularGroupsForPane(paneId) as group, groupIndex}
                  <section class="learning-unit-module" aria-label={group.title ?? "Modul"}>
                    <header class="learning-unit-module__header">
                      <div class="learning-unit-module__copy">
                        <p class="learning-unit-module__index">{moduleDisplayIndex(groupIndex)}</p>
                        <h4 class="learning-unit-module__title">{group.title ?? "Modul"}</h4>
                        <p class="learning-unit-module__meta">{moduleMetaText(group)}</p>
                      </div>
                    </header>

                    {#if group.materials.length}
                      <section class="learning-unit-module__materials" aria-label="Materialien">
                        <div class="learning-unit-module__section-head">
                          <h5>Materialien</h5>
                        </div>
                        <div class="learning-unit-module__section-body">
                          {#each group.materials as entry}
                            {#if entry.item.material}
                              <LearningMaterialCard
                                material={entry.item.material}
                                domId={itemDomId(paneId, entry.item.key)}
                                contextLabel={null}
                                expanded={entry.expanded}
                                onToggle={() => onToggleItem(paneId, entry.item.key)}
                              />
                            {/if}
                          {/each}
                        </div>
                      </section>
                    {/if}

                    <section class="learning-unit-module__tasks" aria-label="Aufgaben">
                      <div class="learning-unit-module__section-head">
                        <h5>Aufgaben</h5>
                      </div>
                      <div class="learning-unit-module__section-body">
                        {#each group.tasks as entry}
                          {#if entry.item.task}
                            {@const task = entry.item.task}
                            <LearningTaskCard
                              {courseId}
                              {task}
                              taskTitle={entry.item.title}
                              contextLabel={null}
                              {unitType}
                              moduleId={entry.item.moduleId ?? moduleId}
                              history={historyByTask[task.id] ?? []}
                              domId={itemDomId(paneId, entry.item.key)}
                              expanded={true}
                              compactLayout={true}
                              submitted={submittedTaskId === task.id}
                              message={submissionMessage}
                              errorMessage={submissionErrorTaskId === task.id ? submissionErrorMessage : null}
                              feedbackPending={feedbackPendingTaskId === task.id}
                              feedbackStatusMessage={feedbackStatusTaskId === task.id ? feedbackStatusMessage : null}
                              pendingIntent={feedbackPendingTaskId === task.id ? pendingSubmissionIntent : null}
                              submissionFocused={submissionFocusByPane[paneId] === entry.item.key}
                              initialSubmissionMode={submissionModeByPane[paneId]}
                              reviewPanelOpen={reviewFocusByPane[paneId] === entry.item.key}
                              enhanceSubmit={enhanceTaskForm?.(task.id, paneId)}
                              onToggle={() => onToggleItem(paneId, entry.item.key)}
                              onToggleReviewPanel={() => onToggleReviewPanel(paneId, task.id)}
                              onEnterSubmissionWorkspace={() => onEnterSubmissionWorkspace(paneId, entry.item.key, "text")}
                              onEnterUploadWorkspace={() => onEnterUploadWorkspace(paneId, entry.item.key)}
                              onExitSubmissionWorkspace={() => onExitSubmissionWorkspace(paneId)}
                              onSubmitUploadFeedback={
                                onSubmitUploadFeedback
                                  ? (payload) => onSubmitUploadFeedback({ ...payload, paneId })
                                  : null
                              }
                            />
                          {/if}
                        {/each}
                      </div>
                    </section>
                  </section>
                {/each}
              </div>
            {:else}
              <div class="learning-unit-pane__stack">
                {#each paneItems[paneId] as entry}
                  {#if entry.item.kind === "material" && entry.item.material}
                    <LearningMaterialCard
                      material={entry.item.material}
                      domId={itemDomId(paneId, entry.item.key)}
                      contextLabel={entry.item.contextLabel}
                      expanded={entry.expanded}
                      onToggle={() => onToggleItem(paneId, entry.item.key)}
                    />
                  {:else if entry.item.kind === "task" && entry.item.task}
                    {@const task = entry.item.task}
                    <LearningTaskCard
                      {courseId}
                      {task}
                      taskTitle={entry.item.title}
                      contextLabel={entry.item.contextLabel}
                      {unitType}
                      moduleId={entry.item.moduleId ?? moduleId}
                      history={historyByTask[task.id] ?? []}
                      domId={itemDomId(paneId, entry.item.key)}
                      expanded={entry.expanded}
                      submitted={submittedTaskId === task.id}
                      message={submissionMessage}
                      errorMessage={submissionErrorTaskId === task.id ? submissionErrorMessage : null}
                      feedbackPending={feedbackPendingTaskId === task.id}
                      feedbackStatusMessage={feedbackStatusTaskId === task.id ? feedbackStatusMessage : null}
                      pendingIntent={feedbackPendingTaskId === task.id ? pendingSubmissionIntent : null}
                      submissionFocused={submissionFocusByPane[paneId] === entry.item.key}
                      initialSubmissionMode={submissionModeByPane[paneId]}
                      reviewPanelOpen={reviewFocusByPane[paneId] === entry.item.key}
                      enhanceSubmit={enhanceTaskForm?.(task.id, paneId)}
                      onToggle={() => onToggleItem(paneId, entry.item.key)}
                      onToggleReviewPanel={() => onToggleReviewPanel(paneId, task.id)}
                      onEnterSubmissionWorkspace={() => onEnterSubmissionWorkspace(paneId, entry.item.key, "text")}
                      onEnterUploadWorkspace={() => onEnterUploadWorkspace(paneId, entry.item.key)}
                      onExitSubmissionWorkspace={() => onExitSubmissionWorkspace(paneId)}
                      onSubmitUploadFeedback={
                        onSubmitUploadFeedback
                          ? (payload) => onSubmitUploadFeedback({ ...payload, paneId })
                          : null
                      }
                    />
                  {/if}
                {/each}
              </div>
            {/if}
          {:else}
            <div class="learning-unit-pane__empty">
              <p class="learning-unit-empty-copy">In diesem Bereich sind aktuell keine Inhalte geöffnet.</p>
            </div>
          {/if}
        </div>
      </section>
    {/each}
  </div>
</section>
