<script lang="ts">
  import type { TeacherUnitsCatalogItem } from "$lib/types/home";

  let { unit }: { unit: TeacherUnitsCatalogItem } = $props();

  const dateFormatter = new Intl.DateTimeFormat("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Berlin"
  });

  function formatUpdatedAt(value: string): string {
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return value;
    }
    return dateFormatter.format(parsed);
  }
</script>

<li class="teacher-units-catalog-row">
  <a class="teacher-units-catalog-row__link" href={unit.href}>
    <div class="teacher-units-catalog-row__meta">
      <span class="teacher-units-catalog-row__kicker">Einheit</span>
      <span class="teacher-units-catalog-row__status">{unit.meta}</span>
    </div>

    <div class="teacher-units-catalog-row__main">
      <strong>{unit.title}</strong>
      {#if unit.topic}
        <p>{unit.topic}</p>
      {/if}
    </div>

    <div class="teacher-units-catalog-row__time">
      <span class="teacher-units-catalog-row__kicker">Aktualisiert</span>
      <span>{formatUpdatedAt(unit.updated_at)}</span>
    </div>
  </a>
</li>
