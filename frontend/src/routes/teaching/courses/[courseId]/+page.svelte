<script lang="ts">
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>{data.home?.course?.title ?? "Kurs"} | GUSTAV</title>
</svelte:head>

<section class="panel">
  <p class="kicker">Kurskontext</p>
  <h2>{data.home?.course?.title ?? "Kurs"}</h2>
  {#if data.home?.course?.id}
    <p class="actions">
      <a href={`/diagnostics/courses/${data.home.course.id}`}>Diagnostik-Matrix öffnen</a>
    </p>
  {/if}

  <div class="summary-grid">
    <article class="card">
      <h3>Mitglieder</h3>
      <ul>
        {#each data.home?.members ?? [] as member}
          <li>{member.name}</li>
        {/each}
      </ul>
    </article>

    <article class="card">
      <h3>Zugeordnete Lerneinheiten</h3>
      <ul>
        {#each data.home?.units ?? [] as unit}
          <li>
            <a href={unit.href}>{unit.position}. {unit.title}</a>
          </li>
        {/each}
      </ul>
    </article>
  </div>
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

  .summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
    gap: 1rem;
    margin-top: 1.5rem;
  }

  .actions {
    margin: 0.75rem 0 0;
  }

  .actions a {
    color: #286983;
  }

  .card {
    padding: 1rem;
    border-radius: 1.1rem;
    background: linear-gradient(160deg, #faf4ed 0%, #fef6eb 100%);
    border: 1px solid #f2e9e1;
  }

  .card ul {
    margin: 0;
    padding-left: 1.1rem;
  }

  .card a {
    color: inherit;
  }
</style>
