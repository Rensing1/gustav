<script lang="ts">
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>Lernraum | GUSTAV</title>
</svelte:head>

<div class="workspace-page">
  <section class="workspace-panel workspace-panel--plain workspace-section workspace-intro">
    <p class="workspace-kicker">Lernraum</p>
    <h2>Deine freigegebenen Kurse stehen direkt bereit.</h2>
    <p class="workspace-lead">
      Der Einstieg bleibt ruhig und nah am eigentlichen Lernen, damit Inhalte
      und nächste Schritte sofort klar sind.
    </p>
  </section>

  <section class="workspace-panel workspace-section">
    {#if data.home?.courses?.length}
      <div class="workspace-list">
        {#each data.home.courses as course}
          <a href={course.href}>
            <strong>{course.title}</strong>
            <p class="workspace-note">Freigegebener Kurs mit Material, Aufgaben und Rückmeldungen.</p>
            <span class="workspace-meta">{course.id}</span>
            <span class="workspace-action">Kurs öffnen</span>
          </a>
        {/each}
      </div>
    {:else}
      <p class="workspace-empty">Noch keine Kurse sichtbar.</p>
    {/if}
  </section>
</div>
