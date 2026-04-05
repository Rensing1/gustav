<script lang="ts">
  import type { Snippet } from "svelte";

  let { children }: { children: Snippet } = $props();
</script>

<ul class="quiet-list">
  {@render children()}
</ul>
