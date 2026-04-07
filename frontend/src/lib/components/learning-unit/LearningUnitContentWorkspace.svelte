<script lang="ts">
  import LearningMaterialCard from "$lib/components/learning-unit/LearningMaterialCard.svelte";
  import LearningTaskCard from "$lib/components/learning-unit/LearningTaskCard.svelte";
  import WorkspaceFrameHeader from "$lib/components/ui/WorkspaceFrameHeader.svelte";
  import WorkspaceOutline from "$lib/components/ui/WorkspaceOutline.svelte";
  import WorkspaceSettingsMenu from "$lib/components/ui/WorkspaceSettingsMenu.svelte";
  import type { SubmitFunction } from "@sveltejs/kit";
  import type {
    ContentGroup,
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
    historyTaskId,
    history,
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
    onExitSubmissionWorkspace
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
    historyTaskId: string | null;
    history: LearningSubmission[];
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
    enhanceTaskForm?: ((taskId: string) => SubmitFunction | undefined) | null;
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

<div class="learning-unit-layout-rail">
  <div class="learning-unit-layout-frame" style={shellStyle}>
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
                  <LearningTaskCard
                    {courseId}
                    task={entry.item.task}
                    taskTitle={entry.item.title}
                    contextLabel={entry.item.contextLabel}
                    {unitType}
                    moduleId={entry.item.moduleId ?? moduleId}
                    historyOpen={historyTaskId === entry.item.task.id}
                    {history}
                    domId={itemDomId(paneId, entry.item.key)}
                    expanded={entry.expanded}
                    submitted={submittedTaskId === entry.item.task.id}
                    message={submissionMessage}
                    errorMessage={submissionErrorTaskId === entry.item.task.id ? submissionErrorMessage : null}
                    feedbackPending={feedbackPendingTaskId === entry.item.task.id}
                    feedbackStatusMessage={feedbackStatusTaskId === entry.item.task.id ? feedbackStatusMessage : null}
                    pendingIntent={feedbackPendingTaskId === entry.item.task.id ? pendingSubmissionIntent : null}
                    submissionFocused={submissionFocusByPane[paneId] === entry.item.key}
                    initialSubmissionMode={submissionModeByPane[paneId]}
                    enhanceSubmit={enhanceTaskForm?.(entry.item.task.id)}
                    onToggle={() => onToggleItem(paneId, entry.item.key)}
                    onEnterSubmissionWorkspace={() => onEnterSubmissionWorkspace(paneId, entry.item.key, "text")}
                    onEnterUploadWorkspace={() => onEnterUploadWorkspace(paneId, entry.item.key)}
                    onExitSubmissionWorkspace={() => onExitSubmissionWorkspace(paneId)}
                  />
                {/if}
              {/each}
            </div>
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
  </div>
</div>
