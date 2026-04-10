<script lang="ts">
  let {
    open = false,
    tocOpen,
    splitView,
    showSplitToggle = true,
    tocWidth,
    workspaceWidth,
    splitRatio,
    tocGap,
    paneGap,
    fontScale,
    onToggleMenu,
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
    onUpdatePaneGap
  }: {
    open?: boolean;
    tocOpen: boolean;
    splitView: boolean;
    showSplitToggle?: boolean;
    tocWidth: number;
    workspaceWidth: number;
    splitRatio: number;
    tocGap: number;
    paneGap: number;
    fontScale: number;
    onToggleMenu: () => void;
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
  } = $props();

  function numericValue(event: Event): number {
    const next = Number((event.currentTarget as HTMLInputElement).value);
    return Number.isFinite(next) ? next : 0;
  }
</script>

<div class="workspace-settings-menu" data-layout-menu-root>
  <button
    aria-expanded={open}
    aria-haspopup="dialog"
    aria-label="Layout-Einstellungen"
    class:workspace-top-action--active={open}
    class="workspace-top-action workspace-top-action--quiet learning-unit-view-toggle"
    title="Layout-Einstellungen"
    type="button"
    onclick={onToggleMenu}
  >
    <svg aria-hidden="true" class="learning-unit-view-toggle__icon" viewBox="0 0 20 20">
      <path d="M10 4.25a1.45 1.45 0 1 0 0.001 2.901A1.45 1.45 0 0 0 10 4.25Z"></path>
      <path d="M10 8.55a1.45 1.45 0 1 0 0.001 2.901A1.45 1.45 0 0 0 10 8.55Z"></path>
      <path d="M10 12.85a1.45 1.45 0 1 0 0.001 2.901A1.45 1.45 0 0 0 10 12.85Z"></path>
    </svg>
  </button>

  {#if open}
    <div class="workspace-settings-menu__panel" role="dialog" aria-label="Layout-Einstellungen">
      <label class="workspace-settings-menu__toggle">
        <span>Inhaltsverzeichnis</span>
        <input class="workspace-settings-menu__checkbox" checked={tocOpen} type="checkbox" onchange={onToggleToc} />
      </label>

      {#if showSplitToggle}
        <label class="workspace-settings-menu__toggle">
          <span>Zwei Ansichten</span>
          <input class="workspace-settings-menu__checkbox" checked={splitView} type="checkbox" onchange={onToggleSplitView} />
        </label>
      {/if}

      <label class="workspace-settings-menu__field">
        <span class="workspace-settings-menu__field-head">
          <span>Breite Inhaltsverzeichnis</span>
          <span class="workspace-settings-menu__value">{tocWidth.toFixed(2)} rem</span>
        </span>
        <div class="workspace-settings-menu__field-controls">
          <input class="workspace-settings-menu__range" type="range" min="0" max="120" step="0.25" value={tocWidth} oninput={(event) => onUpdateTocWidth(numericValue(event))} />
          <input class="workspace-settings-menu__number" type="number" min="0" max="120" step="0.25" value={tocWidth} oninput={(event) => onUpdateTocWidth(numericValue(event))} />
        </div>
      </label>

      <label class="workspace-settings-menu__field">
        <span class="workspace-settings-menu__field-head">
          <span>Breite Arbeitsrahmen</span>
          <span class="workspace-settings-menu__value">{workspaceWidth.toFixed(1)} rem</span>
        </span>
        <div class="workspace-settings-menu__field-controls">
          <input class="workspace-settings-menu__range" type="range" min="16" max="320" step="0.5" value={workspaceWidth} oninput={(event) => onPreviewWorkspaceWidth(numericValue(event))} onchange={(event) => onCommitWorkspaceWidth(numericValue(event))} />
          <input class="workspace-settings-menu__number" type="number" min="16" max="320" step="0.5" value={workspaceWidth} oninput={(event) => onPreviewWorkspaceWidth(numericValue(event))} onchange={(event) => onCommitWorkspaceWidth(numericValue(event))} />
        </div>
      </label>

      <label class="workspace-settings-menu__field">
        <span class="workspace-settings-menu__field-head">
          <span>Schriftgröße</span>
          <span class="workspace-settings-menu__value">{fontScale.toFixed(2)}x</span>
        </span>
        <div class="workspace-settings-menu__field-controls">
          <input class="workspace-settings-menu__range" type="range" min="0.1" max="4" step="0.05" value={fontScale} oninput={(event) => onPreviewFontScale(numericValue(event))} onchange={(event) => onCommitFontScale(numericValue(event))} />
          <input class="workspace-settings-menu__number" type="number" min="0.1" max="4" step="0.05" value={fontScale} oninput={(event) => onPreviewFontScale(numericValue(event))} onchange={(event) => onCommitFontScale(numericValue(event))} />
        </div>
      </label>

      <label class="workspace-settings-menu__field">
        <span class="workspace-settings-menu__field-head">
          <span>Aufteilung links / rechts</span>
          <span class="workspace-settings-menu__value">{splitRatio.toFixed(0)} / {(100 - splitRatio).toFixed(0)}</span>
        </span>
        <div class="workspace-settings-menu__field-controls">
          <input class="workspace-settings-menu__range" disabled={!splitView} type="range" min="0" max="100" step="1" value={splitRatio} oninput={(event) => onUpdateSplitRatio(numericValue(event))} />
          <input class="workspace-settings-menu__number" disabled={!splitView} type="number" min="0" max="100" step="1" value={splitRatio} oninput={(event) => onUpdateSplitRatio(numericValue(event))} />
        </div>
      </label>

      <div class="workspace-settings-menu__section">
        <p class="workspace-settings-menu__section-title">Abstände</p>

        <label class="workspace-settings-menu__field">
          <span class="workspace-settings-menu__field-head">
            <span>Abstand Inhaltsverzeichnis</span>
            <span class="workspace-settings-menu__value">{tocGap.toFixed(1)} rem</span>
          </span>
          <div class="workspace-settings-menu__field-controls">
            <input class="workspace-settings-menu__range" type="range" min="0" max="40" step="0.1" value={tocGap} oninput={(event) => onUpdateTocGap(numericValue(event))} />
            <input class="workspace-settings-menu__number" type="number" min="0" max="40" step="0.1" value={tocGap} oninput={(event) => onUpdateTocGap(numericValue(event))} />
          </div>
        </label>

        <label class="workspace-settings-menu__field">
          <span class="workspace-settings-menu__field-head">
            <span>Abstand Arbeitsflächen</span>
            <span class="workspace-settings-menu__value">{paneGap.toFixed(1)} rem</span>
          </span>
          <div class="workspace-settings-menu__field-controls">
            <input class="workspace-settings-menu__range" type="range" min="0" max="40" step="0.1" value={paneGap} oninput={(event) => onUpdatePaneGap(numericValue(event))} />
            <input class="workspace-settings-menu__number" type="number" min="0" max="40" step="0.1" value={paneGap} oninput={(event) => onUpdatePaneGap(numericValue(event))} />
          </div>
        </label>
      </div>

      <button class="workspace-settings-menu__reset" type="button" onclick={onResetLayout}>
        Standardlayout wiederherstellen
      </button>
    </div>
  {/if}
</div>
