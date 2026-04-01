<script lang="ts">
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>{data.courseTitle} | GUSTAV</title>
</svelte:head>

<div class="workspace-page learning-home learning-course-home">
  <section class="learning-home-header">
    <h2>{data.courseTitle}</h2>
  </section>

  {#if data.units.length}
    <ul class="learning-home-list">
      {#each data.units as row}
        <li>
          <a class="learning-home-card" href={`/learning/courses/${data.courseId}/units/${row.unit.id}`}>
            <strong>{row.unit.title}</strong>
            <span class="learning-home-open">Öffnen</span>
          </a>
        </li>
      {/each}
    </ul>
  {:else}
    <section class="workspace-panel learning-home-empty">
      <p class="workspace-empty">Noch keine Lerneinheiten sichtbar.</p>
    </section>
  {/if}
</div>
