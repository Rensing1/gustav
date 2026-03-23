<script lang="ts">
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>Lernraum | GUSTAV</title>
</svelte:head>

<section class="panel">
  <p class="kicker">Lernraum</p>
  <h2>Deine Kurse</h2>
  <p class="lead">
    Der Lernraum startet mit einem klaren Home-Read-Model statt mit einer
    wiederverwendeten SSR-Seite.
  </p>

  {#if data.home?.courses?.length}
    <div class="course-grid">
      {#each data.home.courses as course}
        <a class="course-card" href={course.href}>
          <strong>{course.title}</strong>
          <span>{course.id}</span>
        </a>
      {/each}
    </div>
  {:else}
    <p class="empty">Noch keine Kurse sichtbar.</p>
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
  .empty {
    margin-top: 0;
  }

  .course-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
    gap: 1rem;
    margin-top: 1.5rem;
  }

  .course-card {
    display: grid;
    gap: 0.45rem;
    padding: 1rem;
    border-radius: 1.1rem;
    text-decoration: none;
    color: inherit;
    background: #faf4ed;
    border: 1px solid #f2e9e1;
  }

  .course-card span,
  .empty {
    color: #797593;
  }
</style>
