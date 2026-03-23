<script lang="ts">
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>{data.unit?.title ?? "Lerneinheit"} | GUSTAV</title>
</svelte:head>

<section class="panel">
  <p class="kicker">Teaching</p>
  <h2>{data.unit?.title ?? "Lerneinheit"}</h2>
  <p class="lead">
    Erste SvelteKit-Detailseite fuer Lerneinheiten. Sie zeigt die Kernstruktur
    bereits ohne in den alten SSR-Editor zurueckzufallen.
  </p>

  <div class="meta-grid">
    <article class="card">
      <h3>Typ</h3>
      <p>{data.unit?.unit_type ?? "linear"}</p>
    </article>
    <article class="card">
      <h3>Zusammenfassung</h3>
      <p>{data.unit?.summary ?? "Noch keine Zusammenfassung hinterlegt."}</p>
    </article>
  </div>

  <article class="card list-card">
    <h3>Abschnitte</h3>
    {#if data.sections.length}
      <ol>
        {#each data.sections as section}
          <li>{section.title}</li>
        {/each}
      </ol>
    {:else}
      <p class="empty">Noch keine Abschnitte vorhanden.</p>
    {/if}
  </article>
</section>

<style>
  .panel {
    max-width: 72rem;
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

  .lead,
  .empty,
  .card p {
    color: #5f5a79;
  }

  .meta-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
    gap: 1rem;
    margin-top: 1.5rem;
  }

  .card {
    padding: 1rem;
    border-radius: 1.1rem;
    background: linear-gradient(160deg, #faf4ed 0%, #fef6eb 100%);
    border: 1px solid #f2e9e1;
  }

  .list-card {
    margin-top: 1rem;
  }

  ol {
    margin: 0;
    padding-left: 1.25rem;
  }
</style>
