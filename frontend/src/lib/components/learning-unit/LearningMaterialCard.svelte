<script lang="ts">
  import type { LearningMaterial } from "$lib/types/learning";

  let { material }: { material: LearningMaterial } = $props();
</script>

<article class="card learning-unit-card">
  <strong>{material.title}</strong>
  {#if material.kind === "markdown"}
    <pre>{material.body_md}</pre>
  {:else}
    <p class="learning-unit-empty-copy">
      Datei-Material · {material.filename_original || material.mime_type || "Download im Umbau"}
    </p>
  {/if}
</article>
