<script lang="ts">
  import type { PageData } from "./$types";
  let { data }: { data: PageData } = $props();
</script>

<svelte:head><title>{data.profile?.learner?.name ?? "Lernendenprofil"} | GUSTAV</title></svelte:head>

<section class="workspace-panel workspace-panel--flat workspace-section diagnostics-panel">
  <div class="workspace-section-header">
    <div class="workspace-section-heading">
      <p class="workspace-kicker">Diagnostik</p>
      <h2>{data.profile?.learner?.name ?? "Lernendenprofil"}</h2>
      <p class="workspace-note">Abgaben und Aufgaben in Deinen Kursen. Öffne eine Lerneinheit für die zugehörige Live-Ansicht.</p>
    </div>
    <a class="workspace-link-action" href="/diagnostics">Kurs wählen</a>
  </div>
  {#if data.profile}
    <div class="diagnostics-summary">
      <article><strong>{data.profile.summary.courses_count}</strong><span>Kurse im Blick</span></article>
      <article><strong>{data.profile.summary.submitted_tasks}</strong><span>Aufgaben mit Abgabe</span></article>
      <article><strong>{data.profile.summary.total_tasks}</strong><span>Aufgaben gesamt</span></article>
    </div>
    <div class="diagnostics-courses">
      {#each data.profile.courses as course}
        <article class="diagnostics-course">
          <div class="workspace-section-header">
            <div class="workspace-section-heading"><p class="workspace-kicker">Kurs</p><h3>{course.title}</h3></div>
            <a class="workspace-link-action" href={course.href}>Zur Kursmatrix</a>
          </div>
          <p class="workspace-note"><strong>{course.submitted_tasks}/{course.total_tasks}</strong> Aufgaben mit Abgabe</p>
          <div class="diagnostics-units">
            {#each course.units as unit}
              <a class="diagnostics-cell" href={unit.href}>
                <span>{unit.position}. {unit.title}</span><strong>{unit.submitted_tasks}/{unit.total_tasks}</strong>
              </a>
            {/each}
          </div>
        </article>
      {/each}
    </div>
  {:else}
    <p class="workspace-empty">Noch keine Diagnostikdaten für dieses Lernendenprofil verfügbar.</p>
  {/if}
</section>
