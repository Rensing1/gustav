<script lang="ts">
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>{data.profile?.learner?.name ?? "Lernendenprofil"} | GUSTAV</title>
</svelte:head>

<section class="panel">
  <div class="header-row">
    <div>
      <p class="kicker">Diagnostik</p>
      <h2>{data.profile?.learner?.name ?? "Lernendenprofil"}</h2>
      <p class="lead">
        Erste lernendenbezogene Diagnostikansicht mit kursuebergreifenden
        Summaries und Unit-Fortschritt aus Lehrkraftsicht.
      </p>
    </div>
    {#if data.profile?.learner?.href}
      <a class="ghost-link" href={data.profile.learner.href}>Neu laden</a>
    {/if}
  </div>

  {#if data.profile}
    <div class="summary-grid">
      <article class="summary-card">
        <strong>{data.profile.summary.courses_count}</strong>
        <span>Kurse im Blick</span>
      </article>
      <article class="summary-card">
        <strong>{data.profile.summary.submitted_tasks}</strong>
        <span>Abgeschlossene Aufgaben</span>
      </article>
      <article class="summary-card">
        <strong>{data.profile.summary.total_tasks}</strong>
        <span>Aufgaben gesamt</span>
      </article>
    </div>

    <div class="course-list">
      {#each data.profile.courses as course}
        <article class="course-card">
          <div class="course-head">
            <div>
              <p class="eyebrow">Kurs</p>
              <h3>{course.title}</h3>
            </div>
            <a class="ghost-link" href={course.href}>Zur Kursmatrix</a>
          </div>

          <p class="progress-note">
            <strong>{course.submitted_tasks}/{course.total_tasks}</strong> Aufgaben erledigt
          </p>

          <div class="unit-grid">
            {#each course.units as unit}
              <a class="unit-chip" href={unit.href}>
                <span>{unit.position}. {unit.title}</span>
                <strong>{unit.submitted_tasks}/{unit.total_tasks}</strong>
              </a>
            {/each}
          </div>
        </article>
      {/each}
    </div>
  {:else}
    <p class="empty">Noch keine Diagnostikdaten fuer dieses Lernendenprofil verfuegbar.</p>
  {/if}
</section>

<style>
  .panel {
    max-width: 78rem;
    background: rgba(255, 250, 243, 0.92);
    border: 1px solid #f2e9e1;
    border-radius: 1.5rem;
    padding: clamp(1.25rem, 3vw, 2rem);
    box-shadow: 0 1.5rem 3rem rgba(87, 82, 121, 0.08);
  }

  .header-row {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: start;
    flex-wrap: wrap;
  }

  .kicker,
  .eyebrow {
    margin: 0 0 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #286983;
    font-size: 0.85rem;
  }

  .lead,
  .empty,
  .progress-note {
    color: #5f5a79;
  }

  .ghost-link {
    align-self: start;
    text-decoration: none;
    color: #286983;
    border: 1px solid #cfe0e7;
    border-radius: 999px;
    padding: 0.6rem 0.9rem;
    background: rgba(255, 255, 255, 0.7);
  }

  .summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
    gap: 0.9rem;
    margin-top: 1.5rem;
  }

  .summary-card,
  .course-card {
    border: 1px solid #ece2d8;
    border-radius: 1.1rem;
    background: linear-gradient(160deg, #faf4ed 0%, #fef6eb 100%);
  }

  .summary-card {
    padding: 1rem;
    display: grid;
    gap: 0.35rem;
  }

  .summary-card strong {
    font-size: 1.8rem;
    color: #1f6f78;
  }

  .course-list {
    display: grid;
    gap: 1rem;
    margin-top: 1.5rem;
  }

  .course-card {
    padding: 1.1rem;
  }

  .course-head {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: start;
    flex-wrap: wrap;
  }

  .course-head h3 {
    margin: 0;
  }

  .unit-grid {
    display: grid;
    gap: 0.75rem;
    grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
    margin-top: 1rem;
  }

  .unit-chip {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    align-items: center;
    text-decoration: none;
    color: inherit;
    border: 1px solid #eadfd4;
    border-radius: 1rem;
    padding: 0.9rem 1rem;
    background: rgba(255, 255, 255, 0.72);
  }

  .unit-chip strong {
    color: #1f6f78;
    white-space: nowrap;
  }
</style>
