<script lang="ts">
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>Live | GUSTAV</title>
</svelte:head>

<section class="panel">
  <p class="kicker">Live</p>
  <h2>Kurs fuer Live-Ansicht waehlen</h2>
  <p class="lead">
    Der alte FastAPI-Live-Picker ist retirtiert. Die Einstiegsauswahl liegt jetzt
    im SvelteKit-Frontend; die tiefere Live-Matrix bleibt vorerst noch im
    Backend-Adapter.
  </p>

  {#if data.courses.length}
    <div class="course-list">
      {#each data.courses as course}
        <a class="course-card" href={`/live/courses/${course.id}`}>
          <strong>{course.title}</strong>
          <span>Live-Einstieg oeffnen</span>
        </a>
      {/each}
    </div>
  {:else}
    <p class="empty">Noch keine Kurse fuer den Live-Raum verfuegbar.</p>
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

  .course-list {
    display: grid;
    gap: 1rem;
    margin-top: 1.5rem;
    grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
  }

  .course-card {
    display: grid;
    gap: 0.4rem;
    padding: 1rem 1.1rem;
    border-radius: 1.1rem;
    text-decoration: none;
    color: inherit;
    background: linear-gradient(160deg, #faf4ed 0%, #fef6eb 100%);
    border: 1px solid #f2e9e1;
  }

  .course-card span {
    color: #286983;
    font-size: 0.92rem;
  }
</style>
