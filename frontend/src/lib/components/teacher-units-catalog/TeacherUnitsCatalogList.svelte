<script lang="ts">
  import type { TeacherUnitsCatalogItem } from "$lib/types/home";

  import TeacherUnitsCatalogRow from "./TeacherUnitsCatalogRow.svelte";

  let {
    resultCount,
    items
  }: {
    resultCount: number;
    items: TeacherUnitsCatalogItem[];
  } = $props();

  const relativeFormatter = new Intl.RelativeTimeFormat("de-DE", { numeric: "auto" });

  function relativeUpdateLabel(values: TeacherUnitsCatalogItem[]): string {
    if (!values.length) {
      return "Kein Update";
    }

    const latest = values.reduce((current, item) => {
      return new Date(item.updated_at).getTime() > new Date(current.updated_at).getTime() ? item : current;
    });
    const latestTime = new Date(latest.updated_at).getTime();
    if (Number.isNaN(latestTime)) {
      return "Kein Update";
    }

    const diffMinutes = Math.round((latestTime - Date.now()) / 60000);
    if (Math.abs(diffMinutes) < 60) {
      return `Update ${relativeFormatter.format(diffMinutes, "minute")}`;
    }

    const diffHours = Math.round(diffMinutes / 60);
    if (Math.abs(diffHours) < 48) {
      return `Update ${relativeFormatter.format(diffHours, "hour")}`;
    }

    const diffDays = Math.round(diffHours / 24);
    return `Update ${relativeFormatter.format(diffDays, "day")}`;
  }
</script>

<section class="teacher-units-catalog-list">
  <div class="teacher-units-catalog-list__meta">
    <p>Zeige {resultCount} Einheiten</p>
    <p>{relativeUpdateLabel(items)}</p>
  </div>

  {#if items.length}
    <div class="teacher-units-catalog-list__columns" aria-hidden="true">
      <span>Titel & Beschreibung</span>
      <span>Kurse</span>
      <span>Update</span>
    </div>

    <ul class="teacher-units-catalog-list__items">
      {#each items as unit (unit.id)}
        <TeacherUnitsCatalogRow {unit} />
      {/each}
    </ul>
  {:else}
    <p class="teacher-units-catalog-list__empty">Noch keine passenden Lerneinheiten gefunden.</p>
  {/if}
</section>
