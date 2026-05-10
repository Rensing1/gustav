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

  function courseSummary(): string {
    if (!unit.courses.length) {
      return "Ohne Kurs";
    }
    const labels = unit.courses
      .map((course) => String(course.title || "").trim())
      .filter((title) => title.length > 0)
      .map((title) => title.split(/\s+/, 1)[0]);

    if (!labels.length) {
      return "Ohne Kurs";
    }

    return labels.join(", ");
  }
</script>

<li class="teacher-units-catalog-row">
  <div class="teacher-units-catalog-row__grid">
    <div class="teacher-units-catalog-row__main">
      <a class="teacher-units-catalog-row__title" href={unit.href}>
        <strong>{unit.title}</strong>
      </a>
      {#if unit.topic}
        <p>{unit.topic}</p>
      {/if}
    </div>

    <div class="teacher-units-catalog-row__courses">
      <span class="teacher-units-catalog-row__kicker">Kurse</span>
      <span class="teacher-units-catalog-row__course-list" title={courseSummary()}>{courseSummary()}</span>
    </div>

    <div class="teacher-units-catalog-row__time">
      <span class="teacher-units-catalog-row__kicker">Aktualisiert</span>
      <span>{formatUpdatedAt(unit.updated_at)}</span>
    </div>

    <div class="teacher-units-catalog-row__actions">
      <a class="workspace-link-action workspace-link-action--danger" href={`${unit.href}?delete=1`}>Löschen</a>
    </div>
  </div>
</li>
