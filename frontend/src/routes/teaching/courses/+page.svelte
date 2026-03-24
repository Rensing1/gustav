<script lang="ts">
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>Kurse | GUSTAV</title>
</svelte:head>

<div class="workspace-page">
  <section class="workspace-panel workspace-panel--plain workspace-section workspace-intro">
    <p class="workspace-kicker">Lehrenden-Welt</p>
    <h2>Kurse</h2>
    <p class="workspace-lead">
      Die Kursliste bleibt bewusst scanbar und ruhig, damit Mitglieder,
      Einheiten und Diagnostik schnell erreichbar sind.
    </p>
  </section>

  <section class="workspace-panel workspace-section">
    {#if data.courses.length}
      <div class="workspace-list">
        {#each data.courses as course}
          <a href={`/teaching/courses/${course.id}`}>
            <strong>{course.title}</strong>
            <p class="workspace-note">Kurskontext mit Einheiten, Mitgliedern und Diagnostik.</p>
            <span class="workspace-meta">{course.id}</span>
            <span class="workspace-action">Kurs öffnen</span>
          </a>
        {/each}
      </div>
    {:else}
      <p class="workspace-empty">Noch keine Kurse vorhanden.</p>
    {/if}
  </section>
</div>
