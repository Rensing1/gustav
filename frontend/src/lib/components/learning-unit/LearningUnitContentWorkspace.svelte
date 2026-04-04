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
    submissionFocusByPane: Record<PaneId, string | null>;
    submissionModeByPane: Record<PaneId, "text" | "upload" | null>;
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

  let layoutMenuOpen = $state(false);

  function numericValue(event: Event): number {
    const next = Number((event.currentTarget as HTMLInputElement).value);
    return Number.isFinite(next) ? next : 0;
  }

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
    {#if layoutMenuEnabled}
      <div class="learning-unit-layout-menu" data-layout-menu-root>
        <button
          aria-expanded={layoutMenuOpen}
          aria-haspopup="dialog"
          aria-label="Layout-Einstellungen"
          class:workspace-top-action--active={layoutMenuOpen}
          class="workspace-top-action workspace-top-action--quiet learning-unit-view-toggle"
          title="Layout-Einstellungen"
          type="button"
          onclick={() => {
            layoutMenuOpen = !layoutMenuOpen;
          }}
        >
          <svg aria-hidden="true" class="learning-unit-view-toggle__icon" viewBox="0 0 20 20">
            <path d="M10 4.25a1.45 1.45 0 1 0 0.001 2.901A1.45 1.45 0 0 0 10 4.25Z"></path>
            <path d="M10 8.55a1.45 1.45 0 1 0 0.001 2.901A1.45 1.45 0 0 0 10 8.55Z"></path>
            <path d="M10 12.85a1.45 1.45 0 1 0 0.001 2.901A1.45 1.45 0 0 0 10 12.85Z"></path>
          </svg>
        </button>

        {#if layoutMenuOpen}
          <div class="learning-unit-layout-menu__panel" role="dialog" aria-label="Layout-Einstellungen">
            <label class="learning-unit-layout-menu__toggle">
              <span>Inhaltsverzeichnis</span>
              <input checked={tocOpen} type="checkbox" onchange={onToggleToc} />
            </label>

            {#if showSplitToggle}
              <label class="learning-unit-layout-menu__toggle">
                <span>Zwei Ansichten</span>
                <input checked={splitView} type="checkbox" onchange={onToggleSplitView} />
              </label>
            {/if}

            <label class="learning-unit-layout-menu__field">
              <span class="learning-unit-layout-menu__field-head">
                <span>Breite Inhaltsverzeichnis</span>
                <span class="learning-unit-layout-menu__value">{tocWidth.toFixed(2)} rem</span>
              </span>
              <div class="learning-unit-layout-menu__field-controls">
                <input
                  type="range"
                  min="0"
                  max="120"
                  step="0.25"
                  value={tocWidth}
                  oninput={(event) => onUpdateTocWidth(numericValue(event))}
                />
                <input
                  class="learning-unit-layout-menu__number"
                  type="number"
                  min="0"
                  max="120"
                  step="0.25"
                  value={tocWidth}
                  oninput={(event) => onUpdateTocWidth(numericValue(event))}
                />
              </div>
            </label>

            <label class="learning-unit-layout-menu__field">
              <span class="learning-unit-layout-menu__field-head">
                <span>Breite Arbeitsrahmen</span>
                <span class="learning-unit-layout-menu__value">{workspaceWidth.toFixed(1)} rem</span>
              </span>
              <div class="learning-unit-layout-menu__field-controls">
                <input
                  type="range"
                  min="16"
                  max="320"
                  step="0.5"
                  value={workspaceWidth}
                  oninput={(event) => onPreviewWorkspaceWidth(numericValue(event))}
                  onchange={(event) => onCommitWorkspaceWidth(numericValue(event))}
                />
                <input
                  class="learning-unit-layout-menu__number"
                  type="number"
                  min="16"
                  max="320"
                  step="0.5"
                  value={workspaceWidth}
                  oninput={(event) => onPreviewWorkspaceWidth(numericValue(event))}
                  onchange={(event) => onCommitWorkspaceWidth(numericValue(event))}
                />
              </div>
            </label>

            <label class="learning-unit-layout-menu__field">
              <span class="learning-unit-layout-menu__field-head">
                <span>Schriftgröße</span>
                <span class="learning-unit-layout-menu__value">{fontScale.toFixed(2)}x</span>
              </span>
              <div class="learning-unit-layout-menu__field-controls">
                <input
                  type="range"
                  min="0.1"
                  max="4"
                  step="0.05"
                  value={fontScale}
                  oninput={(event) => onPreviewFontScale(numericValue(event))}
                  onchange={(event) => onCommitFontScale(numericValue(event))}
                />
                <input
                  class="learning-unit-layout-menu__number"
                  type="number"
                  min="0.1"
                  max="4"
                  step="0.05"
                  value={fontScale}
                  oninput={(event) => onPreviewFontScale(numericValue(event))}
                  onchange={(event) => onCommitFontScale(numericValue(event))}
                />
              </div>
            </label>

            <label class="learning-unit-layout-menu__field">
              <span class="learning-unit-layout-menu__field-head">
                <span>Aufteilung links / rechts</span>
                <span class="learning-unit-layout-menu__value">{splitRatio.toFixed(0)} / {(100 - splitRatio).toFixed(0)}</span>
              </span>
              <div class="learning-unit-layout-menu__field-controls">
                <input
                  disabled={!splitView}
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  value={splitRatio}
                  oninput={(event) => onUpdateSplitRatio(numericValue(event))}
                />
                <input
                  class="learning-unit-layout-menu__number"
                  disabled={!splitView}
                  type="number"
                  min="0"
                  max="100"
                  step="1"
                  value={splitRatio}
                  oninput={(event) => onUpdateSplitRatio(numericValue(event))}
                />
              </div>
            </label>

            <div class="learning-unit-layout-menu__section">
              <p class="learning-unit-layout-menu__section-title">Abstände</p>

              <label class="learning-unit-layout-menu__field">
                <span class="learning-unit-layout-menu__field-head">
                  <span>Abstand Inhaltsverzeichnis</span>
                  <span class="learning-unit-layout-menu__value">{tocGap.toFixed(1)} rem</span>
                </span>
                <div class="learning-unit-layout-menu__field-controls">
                  <input
                    type="range"
                    min="0"
                    max="40"
                    step="0.1"
                    value={tocGap}
                    oninput={(event) => onUpdateTocGap(numericValue(event))}
                  />
                  <input
                    class="learning-unit-layout-menu__number"
                    type="number"
                    min="0"
                    max="40"
                    step="0.1"
                    value={tocGap}
                    oninput={(event) => onUpdateTocGap(numericValue(event))}
                  />
                </div>
              </label>

              <label class="learning-unit-layout-menu__field">
                <span class="learning-unit-layout-menu__field-head">
                  <span>Abstand Arbeitsflächen</span>
                  <span class="learning-unit-layout-menu__value">{paneGap.toFixed(1)} rem</span>
                </span>
                <div class="learning-unit-layout-menu__field-controls">
                  <input
                    type="range"
                    min="0"
                    max="40"
                    step="0.1"
                    value={paneGap}
                    oninput={(event) => onUpdatePaneGap(numericValue(event))}
                  />
                  <input
                    class="learning-unit-layout-menu__number"
                    type="number"
                    min="0"
                    max="40"
                    step="0.1"
                    value={paneGap}
                    oninput={(event) => onUpdatePaneGap(numericValue(event))}
                  />
                </div>
              </label>
            </div>

            <button class="learning-unit-layout-menu__reset" type="button" onclick={onResetLayout}>
              Standardlayout wiederherstellen
            </button>
          </div>
        {/if}
      </div>
    {/if}
  </div>
</section>

<section
  class:learning-unit-content-shell--single={!splitView}
  class:learning-unit-content-shell--toc-closed={!tocOpen}
  class="learning-unit-content-shell"
  style={shellStyle}
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
  </div>
</div>
