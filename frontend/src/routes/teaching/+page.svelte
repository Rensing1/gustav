<script lang="ts">
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>Teaching | GUSTAV</title>
</svelte:head>

<div class="workspace-page">
  <section class="workspace-panel workspace-panel--plain workspace-section workspace-intro workspace-intro--wide">
    <p class="workspace-kicker">Lehrenden-Welt</p>
    <h2>Arbeitsbereiche für den heutigen Unterricht und die Vorbereitung.</h2>
    <p class="workspace-lead">
      Kurse, Einheiten, Diagnostik und Live-Zugriff bleiben in einer ruhigen
      Liste erreichbar, ohne Dashboard-Chrome und ohne Kachelwand.
    </p>
  </section>

  <section class="workspace-panel workspace-section">
    <p class="workspace-label">Arbeitsbereiche</p>
    {#if data.home?.entries?.length}
      <div class="workspace-list">
        {#each data.home.entries as entry}
          <a href={entry.href}>
            <strong>{entry.title}</strong>
            <p class="workspace-note">{entry.description}</p>
            <span class="workspace-action">Bereich öffnen</span>
          </a>
        {/each}
      </div>
    {:else}
      <p class="workspace-empty">Noch keine Lehrenden-Navigation verfügbar.</p>
    {/if}
  </section>
</div>
