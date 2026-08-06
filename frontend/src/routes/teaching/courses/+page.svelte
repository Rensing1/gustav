<script lang="ts">
  import PageActionHead from "$lib/components/ui/PageActionHead.svelte";
  import type { ActionData, PageData } from "./$types";

  let { data, form }: { data: PageData; form?: ActionData } = $props();
  let createDialogOpen = $state(false);
  let selected = $state<string[]>([]);

  $effect(() => {
    createDialogOpen = Boolean(data.showCreateDialog) || Boolean(form?.createCourse);
  });

  function schoolYearLabel(start: number | null): string {
    return start == null ? "Schuljahr fehlt" : `${start}/${String((start + 1) % 100).padStart(2, "0")}`;
  }

  function metadata(course: PageData["courses"][number]): string {
    return [course.subject || "Fach fehlt", course.grade_level || "Jahrgang fehlt", schoolYearLabel(course.school_year_start)].join(" · ");
  }

  function catalogHref(status: "active" | "archived"): string {
    const params = new URLSearchParams();
    if (status === "archived") params.set("status", "archived");
    if (data.filters.query) params.set("q", data.filters.query);
    if (data.filters.subject) params.set("subject", data.filters.subject);
    if (data.filters.schoolYearStart) params.set("school_year_start", String(data.filters.schoolYearStart));
    const query = params.toString();
    return query ? `?${query}` : "/teaching/courses";
  }
</script>

<svelte:head><title>Kurse | GUSTAV</title></svelte:head>

<div class="workspace-page workspace-course-catalog">
  <PageActionHead title="Kurse">
    {#snippet actions()}
      <button class="workspace-link-action" type="button" onclick={() => (createDialogOpen = true)}>Neuer Kurs</button>
    {/snippet}
  </PageActionHead>

  <nav class="workspace-course-catalog__scopes" aria-label="Kursstatus">
    <a class:active={data.status === "active"} aria-current={data.status === "active" ? "page" : undefined} href={catalogHref("active")}>Aktiv</a>
    <a class:active={data.status === "archived"} aria-current={data.status === "archived" ? "page" : undefined} href={catalogHref("archived")}>Archiv</a>
  </nav>

  <form method="GET" class="workspace-course-catalog__filters" aria-label="Kurse filtern">
    {#if data.status === "archived"}<input type="hidden" name="status" value="archived" />{/if}
    <label><span>Suche</span><input name="q" value={data.filters.query} placeholder="Titel oder Fach" /></label>
    <label><span>Fach</span><input name="subject" value={data.filters.subject} placeholder="Alle Fächer" /></label>
    <label><span>Schuljahr</span><input name="school_year_start" type="number" min="2000" max="2200" value={data.filters.schoolYearStart ?? ""} placeholder="Alle" /></label>
    <button class="workspace-text-button" type="submit">Filtern</button>
  </form>

  {#if data.status === "active"}
    <form method="POST" action="?/archiveSelected" class="workspace-course-catalog__list">
      {#if selected.length}
        <div class="workspace-course-catalog__batch">
          <span>{selected.length} ausgewählt</span>
          <button class="workspace-link-action" type="submit">Archivieren</button>
        </div>
      {/if}
      {#each data.courses as course}
        <article class="workspace-course-catalog__row" class:workspace-course-catalog__row--incomplete={!course.metadata_complete}>
          <label class="workspace-course-catalog__select" aria-label={`${course.title} auswählen`}>
            <input type="checkbox" name="course_ids" value={course.id} bind:group={selected} />
          </label>
          <div class="workspace-course-catalog__identity">
            <a href={course.href}><strong>{course.title}</strong></a>
            <span>{metadata(course)}</span>
          </div>
          <span class="workspace-course-catalog__counts">{course.members_count} Mitglieder · {course.units_count} Lerneinheiten</span>
          <a class="workspace-link-action" href={course.href}>{course.members_count === 0 ? "Mitglieder hinzufügen" : course.units_count === 0 ? "Erste Lerneinheit hinzufügen" : "Kurs verwalten"}</a>
        </article>
      {:else}
        <p class="workspace-empty">Keine aktiven Kurse für diese Auswahl.</p>
      {/each}
      {#if form?.archiveSelected?.error}<p class="workspace-form-error">{form.archiveSelected.error}</p>{/if}
    </form>
  {:else}
    <div class="workspace-course-catalog__list">
      {#each data.courses as course, index}
        {#if index === 0 || data.courses[index - 1]?.school_year_start !== course.school_year_start}
          <h2 class="workspace-course-catalog__year">{schoolYearLabel(course.school_year_start)}</h2>
        {/if}
        <article class="workspace-course-catalog__row">
          <div class="workspace-course-catalog__identity">
            <a href={course.href}><strong>{course.title}</strong></a><span>{metadata(course)}</span>
          </div>
          <span class="workspace-course-catalog__counts">{course.members_count} Mitglieder · {course.units_count} Lerneinheiten</span>
          <form method="POST" action="?/restoreCourse">
            <input type="hidden" name="course_id" value={course.id} />
            <button class="workspace-text-button" type="submit">Wiederherstellen</button>
          </form>
        </article>
      {:else}
        <p class="workspace-empty">Das Kursarchiv ist leer.</p>
      {/each}
      {#if form?.restoreCourse?.error}<p class="workspace-form-error">{form.restoreCourse.error}</p>{/if}
    </div>
  {/if}
</div>

{#if createDialogOpen}
  <div class="workspace-modal">
    <button class="workspace-modal-backdrop" type="button" aria-label="Dialog schließen" onclick={() => (createDialogOpen = false)}></button>
    <div class="workspace-modal-card" role="dialog" aria-modal="true" aria-labelledby="create-course-title">
      <div class="workspace-modal-header"><div><p class="workspace-modal-eyebrow">Neuer Kurs</p><h2 id="create-course-title">Kurs erstellen</h2></div><button class="ghost-button" type="button" onclick={() => (createDialogOpen = false)}>Schließen</button></div>
      <form method="POST" action="?/createCourse" class="workspace-form">
        <label class="workspace-field"><span>Titel</span><input name="title" value={form?.createCourse?.values?.title ?? ""} maxlength="200" required /></label>
        <div class="workspace-form-grid">
          <label class="workspace-field"><span>Fach</span><input name="subject" list="course-subjects" value={form?.createCourse?.values?.subject ?? ""} maxlength="100" required /></label>
          <label class="workspace-field"><span>Jahrgang</span><input name="grade_level" list="course-grades" value={form?.createCourse?.values?.gradeLevel ?? ""} maxlength="32" required /></label>
          <label class="workspace-field"><span>Schuljahr (Startjahr)</span><input name="school_year_start" type="number" min="2000" max="2200" value={form?.createCourse?.values?.schoolYearStart ?? new Date().getFullYear()} required /></label>
          <label class="workspace-field"><span>Abschnitt (optional)</span><input name="term" value={form?.createCourse?.values?.term ?? ""} maxlength="32" /></label>
        </div>
        <datalist id="course-subjects"><option value="Informatik"></option><option value="Politik-Wirtschaft"></option><option value="Mathematik"></option><option value="Deutsch"></option></datalist>
        <datalist id="course-grades"><option value="5"></option><option value="6"></option><option value="7"></option><option value="8"></option><option value="9"></option><option value="10"></option><option value="Jahrgangsübergreifend"></option></datalist>
        {#if form?.createCourse?.error}<p class="workspace-form-error">{form.createCourse.error}</p>{/if}
        <div class="workspace-inline-actions"><button class="primary-button" type="submit">Kurs anlegen</button><button class="ghost-button" type="button" onclick={() => (createDialogOpen = false)}>Abbrechen</button></div>
      </form>
    </div>
  </div>
{/if}
