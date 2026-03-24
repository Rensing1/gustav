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
      Die Kursmitgliedschaft ist als eigene SvelteKit-Detailfläche erreichbar und bleibt nah am Kurskontext.
    </p>
  </section>

  <section class="workspace-panel workspace-section">
    <p class="workspace-label">Mitgliederliste</p>
    {#if data.home?.members?.length}
      <div class="workspace-list">
        {#each data.home.members as member}
          <a href={member.href}>
            <strong>{member.name}</strong>
            <p class="workspace-note">Diagnostik und Lernendenprofil bleiben direkt erreichbar.</p>
            <span class="workspace-meta">{member.sub}</span>
          </a>
        {/each}
      </div>
    {:else}
      <p class="workspace-empty">Noch keine Mitglieder sichtbar.</p>
    {/if}
  </section>
</div>
