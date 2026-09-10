<script lang="ts">
  import type { Snippet } from "svelte";
  import { modalFocus } from "./modal-focus";

  type Props = {
    labelledBy: string;
    onClose: () => void;
    children: Snippet;
  };

  let { labelledBy, onClose, children }: Props = $props();
</script>

<div class="workspace-modal workspace-modal--drawer">
  <button class="workspace-modal-backdrop" type="button" aria-label="Seitenleiste schließen" onclick={onClose}></button>

  <div
    use:modalFocus={onClose}
    class="workspace-modal-card workspace-drawer-card"
    role="dialog"
    aria-modal="true"
    aria-labelledby={labelledBy}
  >
    {@render children()}
  </div>
</div>
