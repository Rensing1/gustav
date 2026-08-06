<script lang="ts">
  import { handleBrowserAuthRecovery } from "$lib/utils/browser-auth-recovery";

  type CourseOption = {
    id: string;
    title: string;
  };

  type UnitOption = {
    id: string;
    title: string;
    position: number;
    href: string;
  };

  let { courses }: { courses: CourseOption[] } = $props();

  let selectedCourseId = $state("");
  let selectedUnitId = $state("");
  let units = $state<UnitOption[]>([]);
  let unitsLoading = $state(false);
  let unitsError = $state(false);
  let requestSequence = 0;
  let requestController: AbortController | null = null;

  async function loadUnits(courseId: string): Promise<void> {
    const requestId = ++requestSequence;
    requestController?.abort();
    requestController = courseId ? new AbortController() : null;
    selectedUnitId = "";
    units = [];
    unitsError = false;

    if (!courseId) {
      unitsLoading = false;
      return;
    }

    unitsLoading = true;
    try {
      const response = await fetch(`/api/live/views/courses/${encodeURIComponent(courseId)}/units`, {
        cache: "no-store",
        credentials: "include",
        signal: requestController?.signal,
      });
      if (handleBrowserAuthRecovery(response)) {
        return;
      }
      if (!response.ok) {
        throw new Error(`live_units_failed_${response.status}`);
      }
      const payload = (await response.json()) as { units?: UnitOption[] };
      if (requestId !== requestSequence) {
        return;
      }
      units = Array.isArray(payload.units) ? payload.units : [];
    } catch (error) {
      if (requestId !== requestSequence || (error instanceof DOMException && error.name === "AbortError")) {
        return;
      }
      unitsError = true;
    } finally {
      if (requestId === requestSequence) {
        unitsLoading = false;
      }
    }
  }

  function selectCourse(event: Event): void {
    selectedCourseId = (event.currentTarget as HTMLSelectElement).value;
    void loadUnits(selectedCourseId);
  }

  function retryUnits(): void {
    void loadUnits(selectedCourseId);
  }
</script>

{#if courses.length}
  <form class="teacher-live-launcher" action="/live" method="GET" aria-label="Live-Unterricht öffnen">
    <label class="workspace-field teacher-live-launcher__field">
      <span>Kurs</span>
      <select name="course_id" value={selectedCourseId} onchange={selectCourse}>
        <option value="">Kurs wählen</option>
        {#each courses as course}
          <option value={course.id}>{course.title}</option>
        {/each}
      </select>
    </label>

    <label class="workspace-field teacher-live-launcher__field">
      <span>Lerneinheit</span>
      <select
        name="unit_id"
        value={selectedUnitId}
        disabled={!selectedCourseId || unitsLoading || unitsError || units.length === 0}
        onchange={(event) => (selectedUnitId = event.currentTarget.value)}
      >
        {#if !selectedCourseId}
          <option value="">Zuerst Kurs wählen</option>
        {:else if unitsLoading}
          <option value="">Lerneinheiten werden geladen …</option>
        {:else if unitsError}
          <option value="">Laden fehlgeschlagen</option>
        {:else if !units.length}
          <option value="">Keine Lerneinheiten verfügbar</option>
        {:else}
          <option value="">Lerneinheit wählen</option>
          {#each units as unit}
            <option value={unit.id}>{unit.position}. {unit.title}</option>
          {/each}
        {/if}
      </select>
    </label>

    <div class="teacher-live-launcher__status" aria-live="polite">
      {#if unitsError}
        <p class="workspace-form-error">Lerneinheiten konnten nicht geladen werden.</p>
        <button class="workspace-link-action workspace-link-action--quiet" type="button" onclick={retryUnits}>
          Erneut versuchen
        </button>
      {:else if selectedCourseId && !unitsLoading && !units.length}
        <p class="workspace-empty">Diesem Kurs ist noch keine Lerneinheit zugeordnet.</p>
      {/if}
    </div>

    <button class="workspace-link-action teacher-live-launcher__submit" type="submit" disabled={!selectedCourseId || !selectedUnitId}>
      Live öffnen
    </button>
  </form>
{:else}
  <div class="teacher-live-launcher__empty">
    <p class="workspace-empty">Noch keine Kurse vorhanden.</p>
    <a class="workspace-link-action workspace-link-action--quiet" href="/teaching/courses?create=1">Kurs erstellen</a>
  </div>
{/if}
