<script lang="ts">
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>Live | GUSTAV</title>
</svelte:head>

<div class="workspace-page">
  <section class="workspace-panel workspace-panel--plain workspace-section workspace-intro">
    <p class="workspace-kicker">Live</p>
    <h2>Kurs für die aktuelle Unterrichtssituation wählen.</h2>
    <p class="workspace-lead">
      Der Live-Raum bleibt schnell erfassbar und startet ohne zusätzliche
      Dashboard-Ebene direkt bei den relevanten Kursen.
    </p>
  </section>

  <section class="workspace-panel workspace-section">
    {#if data.courses.length}
      <div class="workspace-list">
        {#each data.courses as course}
          <a href={`/live/courses/${course.id}`}>
            <strong>{course.title}</strong>
            <p class="workspace-note">Direkter Einstieg in die operative Kursübersicht.</p>
            <span class="workspace-action">Live öffnen</span>
          </a>
        {/each}
      </div>
    {:else}
      <p class="workspace-empty">Noch keine Kurse für den Live-Raum verfügbar.</p>
    {/if}
  </section>
</div>
