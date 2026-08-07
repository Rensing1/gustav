<script lang="ts">
  import type { Snippet } from "svelte";

  type Props = {
    labelledBy: string;
    onClose: () => void;
    children: Snippet;
  };

  let { labelledBy, onClose, children }: Props = $props();
  let drawerElement: HTMLElement;

  function handleKeydown(event: KeyboardEvent): void {
    if (event.key !== "Escape" || event.defaultPrevented) {
      return;
    }

    // A later modal may temporarily sit above the drawer. Only the topmost
    // modal may react so an underlying drawer cannot close unexpectedly.
    const modalDialogs = Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"][aria-modal="true"]'));
    if (modalDialogs.at(-1) !== drawerElement) {
      return;
    }

    event.preventDefault();
    onClose();
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="workspace-modal workspace-modal--drawer">
  <button class="workspace-modal-backdrop" type="button" aria-label="Seitenleiste schließen" onclick={onClose}></button>

  <div
    bind:this={drawerElement}
    class="workspace-modal-card workspace-drawer-card"
    role="dialog"
    aria-modal="true"
    aria-labelledby={labelledBy}
  >
    {@render children()}
  </div>
</div>
