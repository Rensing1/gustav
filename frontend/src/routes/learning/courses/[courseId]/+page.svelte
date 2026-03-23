<script lang="ts">
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>Kursraum | GUSTAV</title>
</svelte:head>

<section class="panel">
  <p class="kicker">Kursraum</p>
  <h2>Lerneinheiten</h2>
  <p class="lead">
    Der alte Zwischenstopp ist entfernt. Diese Seite fuehrt direkt in die sichtbaren
    Lerneinheiten des Kurses.
  </p>

  {#if data.units.length}
    <div class="unit-grid">
      {#each data.units as row}
        <a class="unit-card" href={`/learning/courses/${data.courseId}/units/${row.unit.id}`}>
          <span class="meta">#{row.position} · {row.unit.unit_type}</span>
          <strong>{row.unit.title}</strong>
          {#if row.unit.summary}
            <span>{row.unit.summary}</span>
          {/if}
        </a>
      {/each}
    </div>
  {:else}
    <p class="empty">Noch keine Lerneinheiten freigeschaltet.</p>
  {/if}
</section>

<style>
  .panel {
    max-width: 70rem;
    background: rgba(255, 250, 243, 0.92);
    border: 1px solid #f2e9e1;
    border-radius: 1.5rem;
    padding: clamp(1.25rem, 3vw, 2rem);
  }

  .kicker,
  .meta,
  .empty,
  .lead {
    color: #6f6b86;
  }

  .kicker {
    margin: 0 0 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.85rem;
  }

  h2,
  .lead {
    margin-top: 0;
  }

  .unit-grid {
    display: grid;
    gap: 1rem;
    grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
  }

  .unit-card {
    display: grid;
    gap: 0.45rem;
    text-decoration: none;
    color: inherit;
    border-radius: 1.1rem;
    background: #fffdf9;
    border: 1px solid #e9dfd2;
    padding: 1rem;
  }
</style>
