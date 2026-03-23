<script lang="ts">
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>Teaching | GUSTAV</title>
</svelte:head>

<section class="panel">
  <p class="kicker">Teaching</p>
  <h2>Lehrenden-Start</h2>
  <p class="lead">
    Diese Sicht trennt die ersten Lehrenden-Räume als explizites Read-Model vom
    alten HTMX- und SSR-Bestand.
  </p>

  {#if data.home?.entries?.length}
    <div class="entry-grid">
      {#each data.home.entries as entry}
        <a class="entry-card" href={entry.href}>
          <strong>{entry.title}</strong>
          <p>{entry.description}</p>
        </a>
      {/each}
    </div>
  {:else}
    <p class="empty">Noch keine Lehrenden-Navigation verfügbar.</p>
  {/if}
</section>

<style>
  .panel {
    max-width: 64rem;
    background: rgba(255, 250, 243, 0.92);
    border: 1px solid #f2e9e1;
    border-radius: 1.5rem;
    padding: clamp(1.25rem, 3vw, 2rem);
    box-shadow: 0 1.5rem 3rem rgba(87, 82, 121, 0.08);
  }

  .kicker {
    margin: 0 0 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #286983;
    font-size: 0.85rem;
  }

  h2,
  .lead,
  .empty,
  .entry-card p {
    margin-top: 0;
  }

  .entry-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
    gap: 1rem;
    margin-top: 1.5rem;
  }

  .entry-card {
    display: grid;
    gap: 0.6rem;
    padding: 1rem;
    border-radius: 1.1rem;
    text-decoration: none;
    color: inherit;
    background: linear-gradient(160deg, #faf4ed 0%, #fef6eb 100%);
    border: 1px solid #f2e9e1;
  }

  .entry-card p,
  .empty {
    color: #797593;
  }
</style>
