<script lang="ts">
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>{data.home?.course?.title ?? "Kurs"} | GUSTAV</title>
</svelte:head>

<div class="workspace-page">
  <section class="workspace-panel workspace-panel--plain workspace-section workspace-intro">
    <p class="workspace-kicker">Kurskontext</p>
    <p class="workspace-lead">
      Einheiten, Mitglieder und Diagnostik bleiben in einer ruhigen Kursfläche gebündelt.
    </p>
    {#if data.home?.course?.id}
      <p class="workspace-inline-actions">
        <a class="ghost-link" href={`/diagnostics/courses/${data.home.course.id}`}>Diagnostik-Matrix öffnen</a>
        <a class="ghost-link" href={data.home.course.members_href}>Mitglieder öffnen</a>
      </p>
    {/if}
  </section>

  <section class="workspace-panel workspace-section">
    <p class="workspace-label">Zugeordnete Lerneinheiten</p>
    {#if data.home?.units?.length}
      <div class="workspace-list">
        {#each data.home.units as unit}
          <a href={unit.href}>
            <strong>{unit.position}. {unit.title}</strong>
            <p class="workspace-note">Direkter Einstieg in die zugehörige Lehrkraftsicht.</p>
            <span class="workspace-action">Lerneinheit öffnen</span>
          </a>
        {/each}
      </div>
    {:else}
      <p class="workspace-empty">Noch keine Lerneinheiten zugeordnet.</p>
    {/if}
  </section>

  <section class="workspace-panel workspace-section">
    <p class="workspace-label">Mitglieder</p>
    {#if data.home?.members?.length}
      <div class="workspace-list">
        {#each data.home.members as member}
          <a href={member.href}>
            <strong>{member.name}</strong>
            <p class="workspace-note">Lernendenprofil und Kurskontext bleiben direkt erreichbar.</p>
            <span class="workspace-meta">{member.sub}</span>
          </a>
        {/each}
      </div>
    {:else}
      <p class="workspace-empty">Noch keine Mitglieder sichtbar.</p>
    {/if}
  </section>
</div>
