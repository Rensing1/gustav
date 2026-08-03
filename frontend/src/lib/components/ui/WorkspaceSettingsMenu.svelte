<script lang="ts">
  let {
    open = false,
    tocOpen,
    fontScale,
    onToggleMenu,
    onToggleToc,
    onResetLayout,
    onCommitFontScale
  }: {
    open?: boolean;
    tocOpen: boolean;
    fontScale: number;
    onToggleMenu: () => void;
    onToggleToc: () => void;
    onResetLayout: () => void;
    onCommitFontScale: (value: number) => void;
  } = $props();

  function fontOptionActive(value: number): boolean {
    return Math.abs(fontScale - value) < 0.02;
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

      <div class="workspace-settings-menu__section">
        <p class="workspace-settings-menu__section-title">Schriftgröße</p>
        <div class="workspace-settings-menu__font-options" role="group" aria-label="Schriftgröße">
          {#each [
            { label: "Klein", value: 0.9 },
            { label: "Standard", value: 1 },
            { label: "Groß", value: 1.15 }
          ] as option}
            <button
              class:workspace-settings-menu__font-option--active={fontOptionActive(option.value)}
              class="workspace-settings-menu__font-option"
              type="button"
              aria-pressed={fontOptionActive(option.value)}
              onclick={() => onCommitFontScale(option.value)}
            >{option.label}</button>
          {/each}
        </div>
      </div>

      <button class="workspace-settings-menu__reset" type="button" onclick={onResetLayout}>
        Darstellung zurücksetzen
      </button>
    </div>
  {/if}
</div>
