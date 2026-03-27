<script lang="ts">
  import type { ActionData, PageData } from "./$types";

  let { data, form }: { data: PageData; form?: ActionData } = $props();

  let addUnitDialogOpen = $state(false);
  let addMemberDialogOpen = $state(false);
  let courseDrawerOpen = $state(false);
  let membersDrawerOpen = $state(false);
  let memberFilter = $state("");
  let pendingMemberRemoval = $state<string | null>(null);
  let pendingUnitRemoval = $state<string | null>(null);
  let draggedModuleId = $state<string | null>(null);
  let unitOrder = $state<PageData["assignedUnits"]>([]);

  function pageHref(extra: Record<string, string> = {}): string {
    const params = new URLSearchParams(extra);
    const query = params.toString();
    return query ? `?${query}` : "";
  }

  function closeAddUnitDialog(): void {
    addUnitDialogOpen = false;
  }

  function closeAddMemberDialog(): void {
    addMemberDialogOpen = false;
  }

  function closeCourseDrawer(): void {
    courseDrawerOpen = false;
  }

  function closeMembersDrawer(): void {
    membersDrawerOpen = false;
  }

  function formatJoinedAt(value: string): string {
    try {
      return new Intl.DateTimeFormat("de-DE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      }).format(new Date(value));
    } catch {
      return value;
    }
  }

  const filteredMembers = $derived.by(() => {
    const query = memberFilter.trim().toLocaleLowerCase("de-DE");
    if (!query) {
      return data.members;
    }
    return data.members.filter((member) => member.name.toLocaleLowerCase("de-DE").includes(query));
  });

  const memberPreview = $derived(data.members.slice(0, 4));
  const memberDialogQuery = $derived(form?.addMember?.values?.query ?? data.memberSearchQuery);
  const courseFormValues = $derived({
    title: form?.saveCourse?.values?.title ?? data.course.title,
    subject: form?.saveCourse?.values?.subject ?? (data.course.subject ?? ""),
    gradeLevel: form?.saveCourse?.values?.gradeLevel ?? (data.course.grade_level ?? ""),
    term: form?.saveCourse?.values?.term ?? (data.course.term ?? ""),
  });
  const unitOrderChanged = $derived(
    unitOrder.length == data.assignedUnits.length
      && unitOrder.some((unit, index) => unit.module_id != data.assignedUnits[index]?.module_id)
  );

  function onDragStart(moduleId: string): void {
    draggedModuleId = moduleId;
  }

  function moveUnit(moduleId: string, offset: number): void {
    const current = [...unitOrder];
    const sourceIndex = current.findIndex((unit) => unit.module_id == moduleId);
    const targetIndex = sourceIndex + offset;

    if (sourceIndex == -1 || targetIndex < 0 || targetIndex >= current.length) {
      return;
    }

    const [moved] = current.splice(sourceIndex, 1);
    current.splice(targetIndex, 0, moved);
    unitOrder = current.map((unit, index) => ({ ...unit, position: index + 1 }));
  }

  function onDrop(targetModuleId: string): void {
    if (!draggedModuleId || draggedModuleId == targetModuleId) {
      draggedModuleId = null;
      return;
    }

    const current = [...unitOrder];
    const sourceIndex = current.findIndex((unit) => unit.module_id == draggedModuleId);
    const targetIndex = current.findIndex((unit) => unit.module_id == targetModuleId);

    if (sourceIndex == -1 || targetIndex == -1) {
      draggedModuleId = null;
      return;
    }

    const [moved] = current.splice(sourceIndex, 1);
    current.splice(targetIndex, 0, moved);
    unitOrder = current.map((unit, index) => ({ ...unit, position: index + 1 }));
    draggedModuleId = null;
  }

  function resetUnitOrder(): void {
    unitOrder = data.assignedUnits;
  }

  $effect(() => {
    unitOrder = data.assignedUnits;
  });

  $effect(() => {
    addUnitDialogOpen = Boolean(data.showAddUnitDialog) || Boolean(form?.addUnit);
  });

  $effect(() => {
    addMemberDialogOpen = Boolean(data.showAddMemberDialog) || Boolean(form?.addMember);
  });

  $effect(() => {
    courseDrawerOpen = Boolean(data.showCourseDrawer) || Boolean(form?.saveCourse) || Boolean(form?.deleteCourse);
  });

  $effect(() => {
    membersDrawerOpen = Boolean(data.showMembersDrawer) || Boolean(form?.removeMember);
  });
</script>

<svelte:head>
  <title>{data.course.title} | GUSTAV</title>
</svelte:head>

<div class="workspace-page workspace-page--course-context">
  <section class="workspace-composer-header">
    <div class="workspace-composer-copy">
      <a class="workspace-back-link" href="/teaching/courses">Zurück zu Kurse</a>
      <h1>{data.course.title}</h1>
      <p class="workspace-copy">{data.assignedUnits.length} Lerneinheiten · {data.members.length} Mitglieder</p>
    </div>

    <div class="workspace-inline-actions">
      <button class="workspace-link-action workspace-mobile-control" type="button" onclick={() => (membersDrawerOpen = true)}>
        Mitglieder
      </button>
      <button class="workspace-link-action workspace-mobile-control" type="button" onclick={() => (courseDrawerOpen = true)}>
        Kurs
      </button>

      <details class="workspace-overflow-menu">
        <summary aria-label="Weitere Aktionen">
          <span aria-hidden="true">⋯</span>
        </summary>
        <div class="workspace-overflow-popover">
          <a class="workspace-link-action" href={`/diagnostics/courses/${data.course.id}`}>Diagnostik</a>
        </div>
      </details>
    </div>
  </section>

  <div class="workspace-composer-layout">
    <section class="workspace-panel workspace-composer-main">
      <div class="workspace-section-header">
        <div class="workspace-section-heading">
          <p class="workspace-label">Lerneinheiten</p>
          <p class="workspace-note">Ordne und ergänze die Bausteine des Kurses direkt in dieser Liste.</p>
        </div>
        <a class="workspace-link-action" href={pageHref({ "add-unit": "1" })}>Lerneinheit hinzufügen</a>
      </div>

      {#if unitOrder.length}
        <div class="workspace-list" role="list">
          {#each unitOrder as unit, index}
            <div
              class="workspace-manage-row workspace-manage-row--draggable"
              role="listitem"
              draggable="true"
              ondragstart={() => onDragStart(unit.module_id)}
              ondragover={(event) => event.preventDefault()}
              ondrop={() => onDrop(unit.module_id)}
            >
              <div class="workspace-unit-row">
                <a class="workspace-manage-row-link" href={unit.href}>
                  <strong>
                    <span class="workspace-unit-order" aria-label={`Position ${unit.position}`}>{unit.position}</span>
                    <span>{unit.title}</span>
                  </strong>
                </a>
              </div>

              <div class="workspace-unit-controls">
                <span class="workspace-unit-handle" aria-hidden="true">
                  <span class="workspace-drag-handle">⋮⋮</span>
                </span>

                <details class="workspace-row-menu">
                  <summary aria-label={`Aktionen für ${unit.title}`}>
                    <span aria-hidden="true">⋯</span>
                  </summary>
                  <div class="workspace-row-menu-popover">
                    <a class="workspace-link-action" href={unit.href}>Öffnen</a>
                    <button class="workspace-text-button" type="button" onclick={() => moveUnit(unit.module_id, -1)} disabled={index == 0}>
                      Nach oben
                    </button>
                    <button
                      class="workspace-text-button"
                      type="button"
                      onclick={() => moveUnit(unit.module_id, 1)}
                      disabled={index == unitOrder.length - 1}
                    >
                      Nach unten
                    </button>
                    {#if pendingUnitRemoval == unit.module_id}
                      <form method="POST" action="?/removeUnit" class="workspace-row-menu-form">
                        <input name="module_id" type="hidden" value={unit.module_id} />
                        <button class="workspace-text-button workspace-text-button--danger" type="submit">Entfernen bestätigen</button>
                        <button class="workspace-text-button" type="button" onclick={() => (pendingUnitRemoval = null)}>Abbrechen</button>
                      </form>
                    {:else}
                      <button class="workspace-text-button workspace-text-button--danger" type="button" onclick={() => (pendingUnitRemoval = unit.module_id)}>
                        Entfernen
                      </button>
                    {/if}
                  </div>
                </details>
              </div>
            </div>
          {/each}
        </div>

        <form id="reorder-modules-form" method="POST" action="?/reorderModules" class="workspace-form workspace-form--compact">
          {#each unitOrder as unit}
            <input name="module_ids" type="hidden" value={unit.module_id} />
          {/each}

          <div class="workspace-inline-actions">
            <button class="workspace-link-action" type="submit" disabled={!unitOrderChanged}>Reihenfolge speichern</button>
            <button class="workspace-text-button" type="button" onclick={resetUnitOrder} disabled={!unitOrderChanged}>Zurücksetzen</button>
          </div>
        </form>

        <div class="workspace-inline-actions">
          <a class="workspace-link-action" href={pageHref({ "add-unit": "1" })}>Lerneinheit hinzufügen</a>
        </div>
      {:else}
        <p class="workspace-empty">Noch keine Lerneinheiten zugeordnet.</p>
        <a class="workspace-link-action" href={pageHref({ "add-unit": "1" })}>Erste Lerneinheit hinzufügen</a>
      {/if}

      {#if form?.removeUnit?.error}
        <p class="workspace-form-error">{form.removeUnit.error}</p>
      {/if}

      {#if form?.reorderModules?.error}
        <p class="workspace-form-error">{form.reorderModules.error}</p>
      {/if}
    </section>

    <aside class="workspace-composer-sidecar" aria-label="Sekundärer Kontext">
      <section class="workspace-panel workspace-sidecar-block">
        <div class="workspace-section-header">
          <div class="workspace-section-heading">
            <p class="workspace-label">Mitglieder</p>
            <p class="workspace-note">{data.members.length} Lernende sind diesem Kurs zugeordnet.</p>
          </div>
          <button class="workspace-link-action" type="button" onclick={() => (membersDrawerOpen = true)}>Verwalten</button>
        </div>

        <div class="workspace-sidecar-list">
          {#each memberPreview as member}
            <a href={member.href}>
              <strong>{member.name}</strong>
              <span>{formatJoinedAt(member.joined_at)}</span>
            </a>
          {/each}
        </div>
      </section>

      <section class="workspace-panel workspace-sidecar-block">
        <div class="workspace-section-header">
          <div class="workspace-section-heading">
            <p class="workspace-label">Kurs</p>
            <p class="workspace-note">Name und Metadaten bleiben hier bewusst klein.</p>
          </div>
          <button class="workspace-link-action" type="button" onclick={() => (courseDrawerOpen = true)}>Bearbeiten</button>
        </div>

        <div class="workspace-sidecar-meta">
          <div><span>Titel</span><strong>{data.course.title}</strong></div>
          <div><span>Fach</span><strong>{data.course.subject || "Nicht gesetzt"}</strong></div>
          <div><span>Jahrgang</span><strong>{data.course.grade_level || "Nicht gesetzt"}</strong></div>
          <div><span>Term</span><strong>{data.course.term || "Nicht gesetzt"}</strong></div>
        </div>
      </section>
    </aside>
  </div>
</div>

{#if courseDrawerOpen}
  <div class="workspace-modal workspace-modal--drawer">
    <a class="workspace-modal-backdrop" href={pageHref()} aria-label="Drawer schließen"></a>

    <div class="workspace-modal-card workspace-drawer-card" role="dialog" aria-modal="true" aria-labelledby="edit-course-title">
      <div class="workspace-modal-header">
        <div>
          <p class="workspace-modal-eyebrow">{data.course.title}</p>
          <h2 id="edit-course-title">Kurs bearbeiten</h2>
        </div>
        <button class="workspace-text-button" type="button" onclick={closeCourseDrawer}>Schließen</button>
      </div>

      <form method="POST" action="?/saveCourse" class="workspace-form">
        <label class="workspace-field">
          <span>Titel</span>
          <input name="title" type="text" value={courseFormValues.title} required />
        </label>

        <div class="workspace-form-grid">
          <label class="workspace-field">
            <span>Fach</span>
            <input name="subject" type="text" value={courseFormValues.subject} />
          </label>

          <label class="workspace-field">
            <span>Jahrgang</span>
            <input name="grade_level" type="text" value={courseFormValues.gradeLevel} />
          </label>
        </div>

        <label class="workspace-field">
          <span>Term</span>
          <input name="term" type="text" value={courseFormValues.term} />
        </label>

        {#if form?.saveCourse?.error}
          <p class="workspace-form-error">{form.saveCourse.error}</p>
        {/if}

        <div class="workspace-inline-actions">
          <button class="workspace-link-action" type="submit">Speichern</button>
          <a class="workspace-link-action" href={pageHref()}>Abbrechen</a>
        </div>
      </form>

      <form method="POST" action="?/deleteCourse" class="workspace-form workspace-danger-zone">
        <input name="expected_title" type="hidden" value={data.course.title} />
        <p class="workspace-label">Kurs löschen</p>
        <p class="workspace-note">Gib den Kurstitel zur Bestätigung ein. Dieser Schritt entfernt auch die Kurszuordnungen.</p>

        <label class="workspace-field">
          <span>Bestätigung</span>
          <input name="confirmation" type="text" placeholder={data.course.title} />
        </label>

        {#if form?.deleteCourse?.error}
          <p class="workspace-form-error">{form.deleteCourse.error}</p>
        {/if}

        <div class="workspace-inline-actions">
          <button class="workspace-text-button workspace-text-button--danger" type="submit">Kurs endgültig löschen</button>
        </div>
      </form>
    </div>
  </div>
{/if}

{#if membersDrawerOpen}
  <div class="workspace-modal workspace-modal--drawer">
    <a class="workspace-modal-backdrop" href={pageHref()} aria-label="Drawer schließen"></a>

    <div class="workspace-modal-card workspace-drawer-card" role="dialog" aria-modal="true" aria-labelledby="members-drawer-title">
      <div class="workspace-modal-header">
        <div>
          <p class="workspace-modal-eyebrow">{data.course.title}</p>
          <h2 id="members-drawer-title">Mitglieder verwalten</h2>
        </div>
        <button class="workspace-text-button" type="button" onclick={closeMembersDrawer}>Schließen</button>
      </div>

      <div class="workspace-inline-actions">
        <a class="workspace-link-action" href={`/teaching/courses/${data.course.id}/members`}>Mitgliederseite</a>
        <a class="workspace-link-action" href={pageHref({ members: "1", "add-member": "1" })}>Mitglied hinzufügen</a>
      </div>

      <label class="workspace-member-search">
        <span>Mitglieder durchsuchen</span>
        <input bind:value={memberFilter} name="member_filter" placeholder="Name eingeben" type="search" />
      </label>

      {#if filteredMembers.length}
        <div class="workspace-list" role="list">
          {#each filteredMembers as member}
            <div class="workspace-manage-row" role="listitem">
              <a class="workspace-manage-row-link" href={member.href}>
                <strong>{member.name}</strong>
                <p class="workspace-note">Beigetreten am {formatJoinedAt(member.joined_at)}</p>
              </a>

              <div class="workspace-inline-actions">
                <a class="workspace-link-action" href={member.href}>Profil</a>

                {#if pendingMemberRemoval == member.sub}
                  <form method="POST" action="?/removeMember" class="workspace-inline-actions">
                    <input name="student_sub" type="hidden" value={member.sub} />
                    <button class="workspace-text-button workspace-text-button--danger" type="submit">Entfernen bestätigen</button>
                    <button class="workspace-text-button" type="button" onclick={() => (pendingMemberRemoval = null)}>Abbrechen</button>
                  </form>
                {:else}
                  <button class="workspace-text-button workspace-text-button--danger" type="button" onclick={() => (pendingMemberRemoval = member.sub)}>
                    Entfernen
                  </button>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      {:else}
        <p class="workspace-empty">Keine Mitglieder passen zu dieser Suche.</p>
      {/if}

      {#if form?.removeMember?.error}
        <p class="workspace-form-error">{form.removeMember.error}</p>
      {/if}
    </div>
  </div>
{/if}

{#if addMemberDialogOpen}
  <div class="workspace-modal">
    <a class="workspace-modal-backdrop" href={pageHref({ members: "1" })} aria-label="Dialog schließen"></a>

    <div class="workspace-modal-card" role="dialog" aria-modal="true" aria-labelledby="add-member-title">
      <div class="workspace-modal-header">
        <div>
          <p class="workspace-modal-eyebrow">{data.course.title}</p>
          <h2 id="add-member-title">Mitglied hinzufügen</h2>
        </div>
        <button class="workspace-text-button" type="button" onclick={closeAddMemberDialog}>Schließen</button>
      </div>

      <form method="GET" class="workspace-form">
        <input name="members" type="hidden" value="1" />
        <input name="add-member" type="hidden" value="1" />

        <label class="workspace-field">
          <span>Lernende suchen</span>
          <input name="member-q" type="search" value={memberDialogQuery} placeholder="Mindestens zwei Zeichen" />
        </label>

        <div class="workspace-inline-actions">
          <button class="workspace-link-action" type="submit">Suchen</button>
          <a class="workspace-link-action" href={pageHref({ members: "1" })}>Abbrechen</a>
        </div>
      </form>

      {#if memberDialogQuery.trim().length < 2}
        <p class="workspace-note">Gib mindestens zwei Zeichen ein, um passende Lernende zu suchen.</p>
      {:else if data.memberSearchResults.length}
        <div class="workspace-search-results">
          {#each data.memberSearchResults as candidate}
            <form method="POST" action="?/addMember" class="workspace-search-result">
              <input name="student_sub" type="hidden" value={candidate.sub} />
              <input name="member_q" type="hidden" value={memberDialogQuery} />
              <div>
                <strong>{candidate.name}</strong>
                <p class="workspace-note">{candidate.sub}</p>
              </div>
              <button class="workspace-link-action" type="submit">Hinzufügen</button>
            </form>
          {/each}
        </div>
      {:else}
        <p class="workspace-empty">Zu dieser Suche wurde kein weiterer Lernender gefunden.</p>
      {/if}

      {#if form?.addMember?.error}
        <p class="workspace-form-error">{form.addMember.error}</p>
      {/if}
    </div>
  </div>
{/if}

{#if addUnitDialogOpen}
  <div class="workspace-modal">
    <a class="workspace-modal-backdrop" href={pageHref()} aria-label="Dialog schließen"></a>

    <div class="workspace-modal-card" role="dialog" aria-modal="true" aria-labelledby="add-unit-title">
      <div class="workspace-modal-header">
        <div>
          <p class="workspace-modal-eyebrow">{data.course.title}</p>
          <h2 id="add-unit-title">Lerneinheit hinzufügen</h2>
        </div>
        <button class="workspace-text-button" type="button" onclick={closeAddUnitDialog}>Schließen</button>
      </div>

      <form method="POST" action="?/addUnit" class="workspace-form">
        <label class="workspace-field">
          <span>Lerneinheit</span>
          <select name="unit_id" required>
            <option value="">Bitte wählen</option>
            {#each data.availableUnits as unit}
              <option value={unit.id} selected={form?.addUnit?.values?.unitId === unit.id}>
                {unit.title}
              </option>
            {/each}
          </select>
        </label>

        {#if !data.availableUnits.length}
          <p class="workspace-note">Alle verfügbaren Lerneinheiten sind diesem Kurs bereits zugeordnet.</p>
        {/if}

        {#if form?.addUnit?.error}
          <p class="workspace-form-error">{form.addUnit.error}</p>
        {/if}

        <div class="workspace-inline-actions">
          <button class="workspace-link-action" type="submit" disabled={!data.availableUnits.length}>Hinzufügen</button>
          <a class="workspace-link-action" href={pageHref()}>Abbrechen</a>
        </div>
      </form>
    </div>
  </div>
{/if}
