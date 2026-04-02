<script lang="ts">
  import LearningMaterialCard from "$lib/components/learning-unit/LearningMaterialCard.svelte";
  import LearningTaskCard from "$lib/components/learning-unit/LearningTaskCard.svelte";
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
    historyTaskId,
    history,
    itemDomId,
    itemIsVisible,
    itemIsVisibleInPane,
    historyHref,
    onToggleToc,
    onToggleSplitView,
    onSetActivePane,
    onOpenItem,
    onCloseItem
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
    paneItems: Record<PaneId, LearningContentItem[]>;
    historyTaskId: string | null;
    history: LearningSubmission[];
    itemDomId: (paneId: PaneId, itemKey: string) => string;
    itemIsVisible: (itemKey: string) => boolean;
    itemIsVisibleInPane: (itemKey: string, paneId: PaneId) => boolean;
    historyHref: (taskId: string, moduleId: string | null) => string;
    onToggleToc: () => void;
    onToggleSplitView: () => void;
    onSetActivePane: (paneId: PaneId) => void;
    onOpenItem: (itemKey: string) => void;
    onCloseItem: (paneId: PaneId, itemKey: string) => void;
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
    <aside class="workspace-panel learning-unit-toc" aria-label="Inhaltsverzeichnis">
      <header class="learning-unit-toc__header">
        <div class="learning-unit-toc__copy">
          <p class="workspace-label">Navigation</p>
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
                  class:learning-unit-toc__item--open={itemIsVisible(item.key)}
                  class:learning-unit-toc__item--active={itemIsVisibleInPane(item.key, activePane)}
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
      >
        <header class="learning-unit-pane__header">
          <div class="learning-unit-pane__copy">
            <p class="workspace-label">{paneTitle(paneId)}</p>
            <h3>{paneHeading()}</h3>
          </div>
          {#if splitView}
            <button
              class:learning-unit-pane__selector--active={activePane === paneId}
              class="learning-unit-pane__selector"
              type="button"
              onclick={() => onSetActivePane(paneId)}
            >
              {activePane === paneId ? "Aktiv" : "Aktivieren"}
            </button>
          {/if}
        </header>

        {#if paneItems[paneId]?.length}
          <div class="learning-unit-pane__stack">
            {#each paneItems[paneId] as item}
              {#if item.kind === "material" && item.material}
                <LearningMaterialCard
                  material={item.material}
                  domId={itemDomId(paneId, item.key)}
                  contextLabel={item.contextLabel}
                  onClose={() => onCloseItem(paneId, item.key)}
                />
              {:else if item.kind === "task" && item.task}
                <LearningTaskCard
                  {courseId}
                  task={item.task}
                  taskTitle={item.title}
                  contextLabel={item.contextLabel}
                  {unitType}
                  {moduleId}
                  historyHref={historyHref(item.task.id, moduleId)}
                  historyOpen={historyTaskId === item.task.id}
                  {history}
                  domId={itemDomId(paneId, item.key)}
                  onClose={() => onCloseItem(paneId, item.key)}
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
