<script lang="ts">
  import TeacherLiveLauncher from "$lib/components/teacher-home/TeacherLiveLauncher.svelte";
  import PageActionHead from "$lib/components/ui/PageActionHead.svelte";
  import QuietList from "$lib/components/ui/QuietList.svelte";
  import QuietListEntry from "$lib/components/ui/QuietListEntry.svelte";
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();

  const dateFormatter = new Intl.DateTimeFormat("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Berlin",
  });

  function formatUpdatedAt(value: string): string {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : dateFormatter.format(parsed);
  }
</script>

<svelte:head>
  <title>Weiterarbeiten | GUSTAV</title>
</svelte:head>

<div class="workspace-page teacher-home-workstarter">
  <PageActionHead title="Weiterarbeiten" />

  <div class="teacher-home-workstarter__grid">
    <section class="teacher-home-workstarter__section" aria-labelledby="teacher-home-live-title">
      <h2 id="teacher-home-live-title">Unterrichten</h2>
      <TeacherLiveLauncher courses={data.home.courses} />
    </section>

    <section class="teacher-home-workstarter__section" aria-labelledby="teacher-home-authoring-title">
      <div class="workspace-section-header teacher-home-workstarter__section-head">
        <div class="workspace-section-heading">
          <h2 id="teacher-home-authoring-title">Vorbereiten</h2>
        </div>
        <a class="workspace-link-action" href={data.home.create_unit_href}>Neue Lerneinheit</a>
      </div>

      {#if data.home.recent_units.length}
        <p class="workspace-label teacher-home-workstarter__label">Zuletzt bearbeitet</p>
        <QuietList>
          {#each data.home.recent_units as unit}
            <QuietListEntry href={unit.href} title={unit.title} meta={formatUpdatedAt(unit.updated_at)} />
          {/each}
        </QuietList>
      {:else}
        <p class="workspace-empty">Noch keine Lerneinheiten vorhanden.</p>
      {/if}

      <a class="workspace-text-action teacher-home-workstarter__all-units" href={data.home.units_href}>
        Alle Lerneinheiten
      </a>
    </section>
  </div>
</div>
