<script lang="ts">
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>Kurse | GUSTAV</title>
</svelte:head>

<section class="panel">
  <p class="kicker">Teaching</p>
  <h2>Kurse</h2>
  <p class="lead">
    Die Kursliste kommt jetzt direkt aus der API und haengt nicht mehr am
    retirten FastAPI-SSR-Einstieg.
  </p>

  {#if data.courses.length}
    <div class="card-grid">
      {#each data.courses as course}
        <a class="card" href={`/teaching/courses/${course.id}`}>
          <strong>{course.title}</strong>
          <span>{course.id}</span>
        </a>
      {/each}
    </div>
  {:else}
    <p class="empty">Noch keine Kurse vorhanden.</p>
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

  .card-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
    gap: 1rem;
    margin-top: 1.5rem;
  }

  .card {
    display: grid;
    gap: 0.45rem;
    padding: 1rem;
    border-radius: 1.1rem;
    text-decoration: none;
    color: inherit;
    background: linear-gradient(160deg, #faf4ed 0%, #fef6eb 100%);
    border: 1px solid #f2e9e1;
  }

  .card span {
    color: #797593;
  }
</style>
