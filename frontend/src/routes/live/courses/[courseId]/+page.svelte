<script lang="ts">
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>{data.course?.course?.title ?? "Live-Kurs"} | GUSTAV</title>
</svelte:head>

<section class="panel">
  <p class="kicker">Live</p>
  <h2>{data.course?.course?.title ?? "Kurs"}</h2>
  <p class="lead">
    Wähle eine zugeordnete Lerneinheit. Die Matrix selbst läuft jetzt im
    SvelteKit-Raum mit eigenem Read-Model.
  </p>

  {#if data.course?.units?.length}
    <div class="unit-list">
      {#each data.course.units as unit}
        <a class="unit-card" href={`/live/courses/${data.course?.course?.id}/units/${unit.id}`}>
          <strong>{unit.position}. {unit.title}</strong>
          <span>Live-Matrix öffnen</span>
        </a>
      {/each}
    </div>
  {:else}
    <p class="empty">Diesem Kurs sind noch keine Lerneinheiten für Live zugeordnet.</p>
  {/if}
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
  .empty {
    color: #5f5a79;
  }

  .unit-list {
    display: grid;
    gap: 1rem;
    margin-top: 1.5rem;
  }

  .unit-card {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: center;
    padding: 1rem 1.1rem;
    border-radius: 1.1rem;
    text-decoration: none;
    color: inherit;
    background: linear-gradient(160deg, #faf4ed 0%, #fef6eb 100%);
    border: 1px solid #f2e9e1;
  }

  .unit-card span {
    color: #286983;
    font-size: 0.92rem;
    white-space: nowrap;
  }
</style>
