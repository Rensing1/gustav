<script lang="ts">
  import LearningMaterialCard from "$lib/components/learning-unit/LearningMaterialCard.svelte";
  import LearningTaskCard from "$lib/components/learning-unit/LearningTaskCard.svelte";
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
    submissionFocusByPane,
    submissionModeByPane,
    showSplitToggle = true,
    itemDomId,
    onToggleToc,
    onToggleSplitView,
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
    submissionFocusByPane: Record<PaneId, string | null>;
    submissionModeByPane: Record<PaneId, "text" | "upload" | null>;
    showSplitToggle?: boolean;
    itemDomId: (paneId: PaneId, itemKey: string) => string;
    onToggleToc: () => void;
    onToggleSplitView: () => void;
    onSetActivePane: (paneId: PaneId) => void;
    onOpenItem: (itemKey: string) => void;
    onRemoveGroup?: ((groupId: string) => void) | undefined;
    onToggleItem: (paneId: PaneId, itemKey: string) => void;
    onEnterSubmissionWorkspace: (paneId: PaneId, itemKey: string, mode?: "text" | "upload") => void;
    onEnterUploadWorkspace: (paneId: PaneId, itemKey: string) => void;
    onExitSubmissionWorkspace: (paneId: PaneId) => void;
  } = $props();

  function paneHasSubmissionFocus(paneId: PaneId): boolean {
    return submissionFocusByPane[paneId] !== null;
  }

  function tocItemActive(itemKey: string): boolean {
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
</script>

<section class="learning-unit-content-toolbar">
  {#if titleLabel || title || meta}
    <div class="learning-unit-content-toolbar__copy">
      {#if titleLabel}
        <p class="workspace-label">{titleLabel}</p>
      {/if}
      {#if title}
        <h3>{title}</h3>
      {/if}
      {#if meta}
        <p class="learning-unit-content-toolbar__meta">{meta}</p>
      {/if}
    </div>
  {/if}

  <div class="learning-unit-content-toolbar__actions">
    {#if unitType === "linear"}
      <button
        aria-label={tocOpen ? "Inhaltsverzeichnis ausblenden" : "Inhaltsverzeichnis einblenden"}
        class:workspace-top-action--active={tocOpen}
        class="workspace-top-action workspace-top-action--quiet learning-unit-view-toggle"
        title={tocOpen ? "Inhaltsverzeichnis ausblenden" : "Inhaltsverzeichnis einblenden"}
        type="button"
        onclick={onToggleToc}
      >
        <svg aria-hidden="true" class="learning-unit-view-toggle__icon" viewBox="0 0 20 20">
          <rect x="3" y="4" width="4" height="12" rx="0.9"></rect>
          <path d="M10 6.5h7"></path>
          <path d="M10 10h7"></path>
          <path d="M10 13.5h7"></path>
        </svg>
      </button>
    {/if}
    {#if showSplitToggle}
      <button
        aria-label={splitView ? "Eine Ansicht" : "Zwei Ansichten"}
        class:workspace-top-action--active={splitView}
        class="workspace-top-action workspace-top-action--quiet learning-unit-view-toggle"
        title={splitView ? "Eine Ansicht" : "Zwei Ansichten"}
        type="button"
        onclick={onToggleSplitView}
      >
        <svg aria-hidden="true" class="learning-unit-view-toggle__icon" viewBox="0 0 20 20">
          {#if splitView}
            <rect x="2.5" y="4" width="5.5" height="12" rx="1.2"></rect>
            <rect x="12" y="4" width="5.5" height="12" rx="1.2"></rect>
          {:else}
            <rect x="3" y="4" width="14" height="12" rx="1.4"></rect>
          {/if}
        </svg>
      </button>
    {/if}
  </div>
</section>

<section
  class:learning-unit-content-shell--single={!splitView}
  class:learning-unit-content-shell--toc-closed={!tocOpen}
  class="learning-unit-content-shell"
>
  {#if tocOpen}
    <aside class="learning-unit-toc" aria-label="Inhaltsverzeichnis">
      <header class="learning-unit-toc__header">
        <div class="learning-unit-toc__copy">
          <h3>Inhaltsverzeichnis</h3>
        </div>
      </header>

      <div class="learning-unit-toc__body">
        {#each contentGroups as group}
          <section class="learning-unit-toc__group">
            {#if group.title}
              <div class="learning-unit-toc__group-head">
                <p class="learning-unit-toc__group-title">{group.title}</p>
                {#if unitType === "modular" && onRemoveGroup}
                  <button
                    aria-label={`Modul ${group.title} ausblenden`}
                    class="learning-unit-toc__group-remove"
                    title={`Modul ${group.title} ausblenden`}
                    type="button"
                    onclick={() => onRemoveGroup(group.id)}
                  >
                    ×
                  </button>
                {/if}
              </div>
            {/if}
            <div class="learning-unit-toc__items">
              {#each group.items as item}
                <button
                  class:learning-unit-toc__item--active={tocItemActive(item.key)}
                  class="learning-unit-toc__item"
                  type="button"
                  onclick={() => onOpenItem(item.key)}
                >
                  <span class="learning-unit-toc__item-label">{item.title}</span>
                </button>
              {/each}
            </div>
          </section>
        {/each}
      </div>
    </aside>
  {/if}

  <div
    class:learning-unit-pane-grid--single={!splitView}
    class:learning-unit-pane-grid--split={splitView}
    class="learning-unit-pane-grid"
  >
    {#each visiblePaneIds as paneId}
      <section
        class:learning-unit-pane--workspace-mode={paneHasSubmissionFocus(paneId)}
        class:learning-unit-pane--active={activePane === paneId}
        class="learning-unit-pane"
        aria-label={splitView ? (paneId === "left" ? "Linkes Arbeitsfeld" : "Rechtes Arbeitsfeld") : "Arbeitsfeld"}
        use:activateOnPointer={paneId}
      >
        <div
          class:learning-unit-workspace-surface--focused={paneHasSubmissionFocus(paneId)}
          class="learning-unit-workspace-surface"
        >
          {#if paneItems[paneId]?.length}
            <div class:learning-unit-pane__stack--workspace-mode={paneHasSubmissionFocus(paneId)} class="learning-unit-pane__stack">
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
                    submissionFocused={submissionFocusByPane[paneId] === entry.item.key}
                    initialSubmissionMode={submissionModeByPane[paneId]}
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
