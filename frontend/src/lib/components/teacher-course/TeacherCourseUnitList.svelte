<script lang="ts">
  export type TeacherCourseUnit = {
    id: string;
    module_id: string;
    title: string;
    position: number;
    href: string;
  };

  let {
    units,
    canMutate,
    draftModuleIds = [],
    reorderError = null
  }: {
    units: TeacherCourseUnit[];
    canMutate: boolean;
    draftModuleIds?: string[];
    reorderError?: string | null;
  } = $props();

  let draggedModuleId = $state<string | null>(null);
  let pendingRemoval = $state<string | null>(null);
  let unitOrder = $state<TeacherCourseUnit[]>([]);

  function orderedUnits(source: TeacherCourseUnit[], moduleIds: string[]): TeacherCourseUnit[] {
    if (!moduleIds.length) {
      return [...source];
    }

    const byModuleId = new Map(source.map((unit) => [unit.module_id, unit]));
    const restored = moduleIds
      .map((moduleId) => byModuleId.get(moduleId))
      .filter((unit): unit is TeacherCourseUnit => Boolean(unit));
    const restoredIds = new Set(restored.map((unit) => unit.module_id));
    return [...restored, ...source.filter((unit) => !restoredIds.has(unit.module_id))];
  }

  const orderingEnabled = $derived(canMutate && unitOrder.length > 1);
  const unitOrderChanged = $derived(
    unitOrder.length === units.length
      && unitOrder.some((unit, index) => unit.module_id !== units[index]?.module_id)
  );

  function moveUnit(moduleId: string, offset: number): void {
    const current = [...unitOrder];
    const sourceIndex = current.findIndex((unit) => unit.module_id === moduleId);
    const targetIndex = sourceIndex + offset;

    if (sourceIndex === -1 || targetIndex < 0 || targetIndex >= current.length) {
      return;
    }

    const [moved] = current.splice(sourceIndex, 1);
    current.splice(targetIndex, 0, moved);
    unitOrder = current;
  }

  function onDrop(targetModuleId: string): void {
    if (!draggedModuleId || draggedModuleId === targetModuleId) {
      draggedModuleId = null;
      return;
    }

    const current = [...unitOrder];
    const sourceIndex = current.findIndex((unit) => unit.module_id === draggedModuleId);
    const targetIndex = current.findIndex((unit) => unit.module_id === targetModuleId);

    if (sourceIndex === -1 || targetIndex === -1) {
      draggedModuleId = null;
      return;
    }

    const [moved] = current.splice(sourceIndex, 1);
    current.splice(targetIndex, 0, moved);
    unitOrder = current;
    draggedModuleId = null;
  }

  $effect(() => {
    unitOrder = orderedUnits(units, draftModuleIds);
  });
</script>

{#if unitOrder.length}
  <ol class="teacher-course-unit-list" aria-label="Zugeordnete Lerneinheiten">
    {#each unitOrder as unit, index (unit.module_id)}
      <li
        class="teacher-course-unit-list__row"
        aria-label={unit.title}
        draggable={orderingEnabled}
        ondragstart={() => (draggedModuleId = unit.module_id)}
        ondragover={(event) => event.preventDefault()}
        ondrop={() => onDrop(unit.module_id)}
      >
        <div class="teacher-course-unit-list__identity">
          {#if orderingEnabled}
            <span class="teacher-course-unit-list__handle" aria-label={`Reihenfolge von ${unit.title} ändern`}>⠿</span>
          {/if}
          <span class="teacher-course-unit-list__position" aria-label={`Position ${index + 1}`}>{index + 1}</span>
          <a href={unit.href}>{unit.title}</a>
        </div>

        <details class="workspace-row-menu">
          <summary aria-label={`Aktionen für ${unit.title}`}><span aria-hidden="true">⋯</span></summary>
          <div class="workspace-row-menu-popover">
            <a class="workspace-link-action" href={unit.href}>Öffnen</a>
            {#if orderingEnabled}
              <button class="workspace-text-button" type="button" onclick={() => moveUnit(unit.module_id, -1)} disabled={index === 0}>Nach oben</button>
              <button class="workspace-text-button" type="button" onclick={() => moveUnit(unit.module_id, 1)} disabled={index === unitOrder.length - 1}>Nach unten</button>
            {/if}
            {#if canMutate && pendingRemoval === unit.module_id}
              <form method="POST" action="?/removeUnit" class="workspace-row-menu-form">
                <input name="module_id" type="hidden" value={unit.module_id} />
                <button class="workspace-text-button workspace-text-button--danger" type="submit">Entfernen bestätigen</button>
                <button class="workspace-text-button" type="button" onclick={() => (pendingRemoval = null)}>Abbrechen</button>
              </form>
            {:else if canMutate}
              <button class="workspace-text-button workspace-text-button--danger" type="button" onclick={() => (pendingRemoval = unit.module_id)}>Entfernen</button>
            {/if}
          </div>
        </details>
      </li>
    {/each}
  </ol>

  {#if unitOrderChanged}
    <form method="POST" action="?/reorderModules" class="teacher-course-unit-list__changes">
      {#each unitOrder as unit}
        <input name="module_ids" type="hidden" value={unit.module_id} />
      {/each}
      <div>
        <strong>Reihenfolge geändert</strong>
        {#if reorderError}<p class="workspace-form-error" role="alert">{reorderError}</p>{/if}
      </div>
      <div class="workspace-inline-actions">
        <button class="workspace-link-action" type="submit">Reihenfolge speichern</button>
        <button class="workspace-text-button" type="button" onclick={() => (unitOrder = [...units])}>Verwerfen</button>
      </div>
    </form>
  {/if}
{:else}
  <p class="teacher-course-unit-list__empty">Noch keine Lerneinheiten</p>
{/if}
