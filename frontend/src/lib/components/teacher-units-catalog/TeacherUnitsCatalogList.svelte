<script lang="ts">
  import type { TeacherUnitsCatalogItem } from "$lib/types/home";

  import TeacherUnitsCatalogRow from "./TeacherUnitsCatalogRow.svelte";

  let {
    activeViewLabel,
    resultCount,
    items
  }: {
    activeViewLabel: string;
    resultCount: number;
    items: TeacherUnitsCatalogItem[];
  } = $props();
</script>

<section class="teacher-units-catalog-list">
  <div class="teacher-units-catalog-list__header">
    <div>
      <p class="teacher-units-catalog-list__eyebrow">Bestand</p>
      <h2>{activeViewLabel}</h2>
    </div>
    <p class="teacher-units-catalog-list__count">{resultCount} Einheiten</p>
  </div>

  {#if items.length}
    <div class="teacher-units-catalog-list__columns" aria-hidden="true">
      <span>Status</span>
      <span>Titel & Thema</span>
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
