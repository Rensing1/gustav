<script lang="ts">
  import type { ActionData, PageData } from "./$types";

  let { data, form }: { data: PageData; form?: ActionData } = $props();
  let createDialogOpen = $state(false);

  function closeCreateDialog(): void {
    createDialogOpen = false;
  }

  $effect(() => {
    createDialogOpen = Boolean(data.showCreateDialog) || Boolean(form?.createCourse);
  });

  function courseMeta(course: PageData["courses"][number]): string | null {
    const parts = [course.subject, course.grade_level, course.term].filter((value) =>
      Boolean(String(value || "").trim())
    );

    return parts.length ? parts.join(" · ") : null;
  }
</script>

<svelte:head>
  <title>Kurse | GUSTAV</title>
</svelte:head>

<div class="workspace-page">
  {#if data.courses.length}
    <div class="workspace-grid workspace-grid--courses">
      {#each data.courses as course}
        <a class="workspace-link-card workspace-link-card--course" href={`/teaching/courses/${course.id}`}>
          <strong>{course.title}</strong>
          <div class="workspace-metrics" aria-label="Kurskennzahlen">
            <span>{course.members_count} Mitglieder</span>
            <span>{course.units_count} Lerneinheiten</span>
          </div>
          {#if courseMeta(course)}
            <p class="workspace-note">{courseMeta(course)}</p>
          {/if}
        </a>
      {/each}
    </div>
  {:else}
    <p class="workspace-empty">Noch keine Kurse vorhanden. Lege den ersten Kurs direkt hier an.</p>
  {/if}
</div>

{#if createDialogOpen}
  <div class="workspace-modal">
    <button
      class="workspace-modal-backdrop"
      type="button"
      aria-label="Dialog schließen"
      onclick={closeCreateDialog}
    ></button>

    <div class="workspace-modal-card" role="dialog" aria-modal="true" aria-labelledby="create-course-title">
      <div class="workspace-modal-header">
        <div>
          <p class="workspace-modal-eyebrow">Neuer Kurs</p>
          <h2 id="create-course-title">Kurs erstellen</h2>
        </div>
        <button class="ghost-button" type="button" onclick={closeCreateDialog}>Schließen</button>
      </div>

      <form method="POST" class="workspace-form">
        <label class="workspace-field">
          <span>Titel</span>
          <input
            name="title"
            type="text"
            value={form?.createCourse?.values?.title ?? ""}
            maxlength="200"
            required
          />
        </label>

        <div class="workspace-form-grid">
          <label class="workspace-field">
            <span>Fach</span>
            <input
              name="subject"
              type="text"
              value={form?.createCourse?.values?.subject ?? ""}
              maxlength="100"
            />
          </label>

          <label class="workspace-field">
            <span>Jahrgang</span>
            <input
              name="grade_level"
              type="text"
              value={form?.createCourse?.values?.gradeLevel ?? ""}
              maxlength="32"
            />
          </label>

          <label class="workspace-field">
            <span>Abschnitt</span>
            <input
              name="term"
              type="text"
              value={form?.createCourse?.values?.term ?? ""}
              maxlength="32"
            />
          </label>
        </div>

        {#if form?.createCourse?.error}
          <p class="workspace-form-error">{form.createCourse.error}</p>
        {/if}

        <div class="workspace-inline-actions">
          <button class="primary-button" type="submit">Kurs anlegen</button>
          <button class="ghost-button" type="button" onclick={closeCreateDialog}>Abbrechen</button>
        </div>
      </form>
    </div>
  </div>
{/if}
