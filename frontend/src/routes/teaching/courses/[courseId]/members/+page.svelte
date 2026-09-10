<script lang="ts">
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>Mitglieder | GUSTAV</title>
</svelte:head>

<div class="workspace-page">
  <section class="workspace-panel workspace-panel--plain workspace-section workspace-intro">
    <p class="workspace-kicker">{data.home?.course?.title ?? "Kurs"}</p>
    <p class="workspace-lead">
      Öffne einen Namen, um das Lernendenprofil anzusehen. Mitgliedschaften verwaltest Du in der Kursübersicht.
    </p>
  </section>

  <a class="workspace-link-action" href={data.home.course.href}>Mitglieder verwalten</a>

  <section class="workspace-panel workspace-panel--flat workspace-section">
    <p class="workspace-label">Mitgliederliste</p>
    {#if data.home?.members?.length}
      <div class="workspace-list">
        {#each data.home.members as member}
          <a href={member.href}>
            <strong>{member.name}</strong>
            <p class="workspace-note">Lernendenprofil öffnen</p>
          </a>
        {/each}
      </div>
    {:else}
      <p class="workspace-empty">Noch keine Mitglieder sichtbar.</p>
    {/if}
  </section>
</div>
