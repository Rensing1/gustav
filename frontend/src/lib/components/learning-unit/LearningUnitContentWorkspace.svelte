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
    submissionErrorTaskId = null,
    submissionErrorMessage = null,
    submissionFocusByPane,
    itemDomId,
    onToggleToc,
    onToggleSplitView,
    onSetActivePane,
    onOpenItem,
    onToggleItem,
    onEnterSubmissionWorkspace,
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
    submissionErrorTaskId?: string | null;
    submissionErrorMessage?: string | null;
    submissionFocusByPane: Record<PaneId, string | null>;
    itemDomId: (paneId: PaneId, itemKey: string) => string;
    onToggleToc: () => void;
    onToggleSplitView: () => void;
    onSetActivePane: (paneId: PaneId) => void;
    onOpenItem: (itemKey: string) => void;
    onToggleItem: (paneId: PaneId, itemKey: string) => void;
    onEnterSubmissionWorkspace: (paneId: PaneId, itemKey: string) => void;
    onExitSubmissionWorkspace: (paneId: PaneId) => void;
  } = $props();

  function paneTitle(paneId: PaneId): string {
    if (!splitView) {
      return "Arbeitsbereich";
    }
    return paneId === "left" ? "Ansicht A" : "Ansicht B";
  }

  function paneHeading(): string {
    return splitView ? "Geöffnete Inhalte" : "Arbeitsbereich";
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

<section class="workspace-panel learning-unit-content-toolbar">
  <div class="learning-unit-content-toolbar__copy">
    <p class="workspace-label">{titleLabel}</p>
    <h3>{title}</h3>
    {#if meta}
      <p class="learning-unit-content-toolbar__meta">{meta}</p>
    {/if}
  </div>

  <div class="learning-unit-content-toolbar__actions">
    <button class="workspace-top-action workspace-top-action--quiet" type="button" onclick={onToggleToc}>
      {tocOpen ? "Inhaltsverzeichnis ausblenden" : "Inhaltsverzeichnis"}
    </button>
    <button
      class:workspace-top-action--active={splitView}
      class="workspace-top-action workspace-top-action--quiet"
      type="button"
      onclick={onToggleSplitView}
    >
      {splitView ? "Eine Ansicht" : "Zwei Ansichten"}
    </button>
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
              <p class="learning-unit-toc__group-title">{group.title}</p>
            {/if}
            <div class="learning-unit-toc__items">
              {#each group.items as item}
                <button
                  class="learning-unit-toc__item"
                  type="button"
                  onclick={() => onOpenItem(item.key)}
                >
                  <span>{item.title}</span>
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
        class:learning-unit-pane--active={activePane === paneId}
        class="workspace-panel learning-unit-pane"
        aria-label={paneTitle(paneId)}
        use:activateOnPointer={paneId}
      >
        <header class="learning-unit-pane__header">
          <div class="learning-unit-pane__copy">
            <p class="workspace-label">{paneTitle(paneId)}</p>
            <h3>{paneHeading()}</h3>
          </div>
        </header>

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
                  errorMessage={submissionErrorTaskId === entry.item.task.id ? submissionErrorMessage : null}
                  submissionFocused={submissionFocusByPane[paneId] === entry.item.key}
                  onToggle={() => onToggleItem(paneId, entry.item.key)}
                  onEnterSubmissionWorkspace={() => onEnterSubmissionWorkspace(paneId, entry.item.key)}
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
      </section>
    {/each}
  </div>
</section>
