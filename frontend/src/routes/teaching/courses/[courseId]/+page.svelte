<script lang="ts">
  import { replaceState } from "$app/navigation";
  import { page } from "$app/state";
  import TeacherCourseUnitList from "$lib/components/teacher-course/TeacherCourseUnitList.svelte";
  import PageActionHead from "$lib/components/ui/PageActionHead.svelte";
  import WorkspaceDrawer from "$lib/components/ui/WorkspaceDrawer.svelte";
  import { withoutQueryParameters } from "$lib/components/ui/workspace-drawer-url";
  import type { ActionData, PageData } from "./$types";

  let { data, form }: { data: PageData; form?: ActionData } = $props();

  let addUnitDialogOpen = $state(false);
  let addMemberDialogOpen = $state(false);
  let courseDrawerOpen = $state(false);
  let membersDrawerOpen = $state(false);
  let memberFilter = $state("");
  let pendingMemberRemoval = $state<string | null>(null);

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

  function openCourseDrawer(): void {
    courseDrawerOpen = true;
  }

  function closeCourseDrawer(): void {
    courseDrawerOpen = false;
    removeDrawerQuery("course");
  }

  function closeMembersDrawer(): void {
    membersDrawerOpen = false;
    removeDrawerQuery("members", "add-member", "member-q");
  }

  function removeDrawerQuery(...names: string[]): void {
    if (typeof window === "undefined") {
      return;
    }

    const currentHref = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    const nextHref = withoutQueryParameters(window.location.href, names);
    if (nextHref !== currentHref) {
      replaceState(nextHref, page.state);
    }
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

  const memberDialogQuery = $derived(form?.addMember?.values?.query ?? data.memberSearchQuery);
  const courseFormValues = $derived({
    title: form?.saveCourse?.values?.title ?? data.course.title,
    subject: form?.saveCourse?.values?.subject ?? (data.course.subject ?? ""),
    gradeLevel: form?.saveCourse?.values?.gradeLevel ?? (data.course.grade_level ?? ""),
    term: form?.saveCourse?.values?.term ?? (data.course.term ?? ""),
    schoolYearStart: form?.saveCourse?.values?.schoolYearStart ?? (data.course.school_year_start ?? ""),
  });
  const readOnly = $derived(data.course.status === "archived");
  const canMutate = $derived(!readOnly && data.course.metadata_complete);
  const missingMetadata = $derived([
    ...(!data.course.subject ? ["Fach"] : []),
    ...(!data.course.grade_level ? ["Jahrgang"] : []),
    ...(data.course.school_year_start == null ? ["Schuljahr"] : [])
  ]);
  const courseMetadata = $derived([
    data.course.subject,
    data.course.grade_level === "Jahrgangsübergreifend"
      ? data.course.grade_level
      : data.course.grade_level ? `Jahrgang ${data.course.grade_level}` : null,
    data.course.school_year_start == null
      ? null
      : `${data.course.school_year_start}/${String((data.course.school_year_start + 1) % 100).padStart(2, "0")}`,
    `${data.assignedUnits.length} ${data.assignedUnits.length === 1 ? "Lerneinheit" : "Lerneinheiten"}`,
    `${data.members.length} ${data.members.length === 1 ? "Lernender" : "Lernende"}`
  ].filter((value): value is string => Boolean(value)).join(" · "));

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

<div class="workspace-page teacher-course-workspace">
  <PageActionHead backHref="/teaching/courses" backLabel="← Kurse" title={data.course.title} copy={courseMetadata} />

  {#if readOnly}
    <div class="teacher-course-workspace__status" role="status">
      <strong>Archiviert · schreibgeschützt</strong>
    </div>
  {/if}

  {#if missingMetadata.length}
    <div class="teacher-course-workspace__status teacher-course-workspace__status--warning" role="status">
      <span><strong>Kursdaten unvollständig:</strong> {missingMetadata.join(", ")}</span>
      <a class="workspace-text-button" href={pageHref({ course: "1" })} onclick={openCourseDrawer}>Ergänzen</a>
    </div>
  {/if}

  <section class="teacher-course-workspace__section" aria-labelledby="course-units-title">
    <div class="teacher-course-workspace__section-head">
      <div>
        <h2 id="course-units-title">Lerneinheiten</h2>
        <span>{data.assignedUnits.length}</span>
      </div>
      {#if canMutate}
        <a class="workspace-link-action" href={pageHref({ "add-unit": "1" })}>Lerneinheit hinzufügen</a>
      {/if}
    </div>

    <TeacherCourseUnitList
      units={data.assignedUnits}
      {canMutate}
      draftModuleIds={form?.reorderModules?.moduleIds ?? []}
      reorderError={form?.reorderModules?.error ?? null}
    />

    {#if form?.removeUnit?.error}
      <p class="workspace-form-error" role="alert">{form.removeUnit.error}</p>
    {/if}
  </section>

  <section class="teacher-course-workspace__section" aria-labelledby="course-members-title">
    <div class="teacher-course-workspace__management-row">
      <div>
        <h2 id="course-members-title">Mitglieder</h2>
        <p>{data.members.length} {data.members.length === 1 ? "Lernender" : "Lernende"}</p>
      </div>
      <button class="workspace-link-action" type="button" onclick={() => (membersDrawerOpen = true)}>
        {canMutate ? "Mitglieder verwalten" : "Mitglieder ansehen"}
      </button>
    </div>
  </section>

  <section class="teacher-course-workspace__section" aria-labelledby="course-ai-usage-title">
    <div class="teacher-course-workspace__management-row">
      <div>
        <h2 id="course-ai-usage-title">KI-Nutzung</h2>
        <p>Input-, Output- und Gesamttokens des Kurses</p>
      </div>
      <a class="workspace-link-action" href={`/teaching/courses/${data.course.id}/ai-usage`}>KI-Nutzung öffnen</a>
    </div>
  </section>

  <section class="teacher-course-workspace__section" aria-labelledby="course-settings-title">
    <div class="teacher-course-workspace__management-row">
      <div>
        <h2 id="course-settings-title">Kurseinstellungen</h2>
        <p>Stammdaten und Kursstatus</p>
      </div>
      <a class="workspace-link-action" href={pageHref({ course: "1" })} onclick={openCourseDrawer}>Kurs bearbeiten</a>
    </div>
  </section>
</div>

{#if courseDrawerOpen}
  <WorkspaceDrawer labelledBy="edit-course-title" onClose={closeCourseDrawer}>
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

        <label class="workspace-field">
          <span>Schuljahr (Startjahr)</span>
          <input name="school_year_start" type="number" min="2000" max="2200" value={courseFormValues.schoolYearStart} required />
        </label>

        <div class="workspace-form-grid">
          <label class="workspace-field">
            <span>Fach</span>
            <input name="subject" type="text" list="course-detail-subjects" value={courseFormValues.subject} required />
          </label>

          <label class="workspace-field">
            <span>Jahrgang</span>
            <input name="grade_level" type="text" list="course-detail-grades" value={courseFormValues.gradeLevel} required />
          </label>
        </div>

        <datalist id="course-detail-subjects">
          <option value="Informatik"></option>
          <option value="Politik-Wirtschaft"></option>
          <option value="Mathematik"></option>
          <option value="Deutsch"></option>
        </datalist>
        <datalist id="course-detail-grades">
          <option value="5"></option><option value="6"></option><option value="7"></option>
          <option value="8"></option><option value="9"></option><option value="10"></option>
          <option value="Jahrgangsübergreifend"></option>
        </datalist>

        {#if courseFormValues.term}
          <label class="workspace-field">
            <span>Frühere Abschnittsangabe</span>
            <input name="term" type="text" value={courseFormValues.term} />
          </label>
        {:else}
          <input name="term" type="hidden" value="" />
        {/if}

        {#if form?.saveCourse?.error}
          <p class="workspace-form-error">{form.saveCourse.error}</p>
        {/if}

        <div class="workspace-inline-actions">
          <button class="workspace-link-action" type="submit">Speichern</button>
          <a class="workspace-link-action" href={pageHref()}>Abbrechen</a>
        </div>
      </form>

      <form method="POST" action={readOnly ? "?/restoreCourse" : "?/archiveCourse"} class="workspace-form">
        <p class="workspace-label">{readOnly ? "Kurs wiederherstellen" : "Kurs archivieren"}</p>
        <p class="workspace-note">{readOnly ? "Nur verwenden, um eine versehentliche Archivierung zu korrigieren." : "Beendet die aktive Unterrichtsnutzung und erhält Lernleistungen schreibgeschützt."}</p>
        {#if form?.archiveCourse?.error}<p class="workspace-form-error">{form.archiveCourse.error}</p>{/if}
        {#if form?.restoreCourse?.error}<p class="workspace-form-error">{form.restoreCourse.error}</p>{/if}
        <button class="workspace-link-action" type="submit">{readOnly ? "Wiederherstellen" : "Archivieren"}</button>
      </form>

      <form method="POST" action="?/deleteCourse" class="workspace-form workspace-danger-zone">
        <input name="expected_title" type="hidden" value={data.course.title} />
        <p class="workspace-label">Kurs löschen</p>
        <p class="workspace-note">Unwiderruflich betroffen: {data.deletionImpact?.members_count ?? 0} Mitgliedschaften, {data.deletionImpact?.submissions_count ?? 0} Abgaben, {data.deletionImpact?.dialogs_count ?? 0} Dialoge und {data.deletionImpact?.files_count ?? 0} Dateien.</p>

        <label class="workspace-field">
          <span>Bestätigung</span>
          <input name="confirmation" type="text" placeholder={data.course.title} />
        </label>

        <label class="workspace-field workspace-checkbox-field">
          <input name="confirm_student_data_loss" type="checkbox" value="yes" />
          <span>Ich bestätige den unwiderruflichen Verlust sämtlicher Schülerdaten dieses Kurses.</span>
        </label>

        {#if form?.deleteCourse?.error}
          <p class="workspace-form-error">{form.deleteCourse.error}</p>
        {/if}

        <div class="workspace-inline-actions">
          <button class="workspace-text-button workspace-text-button--danger" type="submit">Kurs endgültig löschen</button>
        </div>
      </form>
  </WorkspaceDrawer>
{/if}

{#if membersDrawerOpen}
  <WorkspaceDrawer labelledBy="members-drawer-title" onClose={closeMembersDrawer}>
      <div class="workspace-modal-header">
        <div>
          <p class="workspace-modal-eyebrow">{data.course.title}</p>
          <h2 id="members-drawer-title">{canMutate ? "Mitglieder verwalten" : "Mitglieder ansehen"}</h2>
        </div>
        <button class="workspace-text-button" type="button" onclick={closeMembersDrawer}>Schließen</button>
      </div>

      {#if canMutate}
        <div class="workspace-inline-actions">
          <a class="workspace-link-action" href={pageHref({ members: "1", "add-member": "1" })}>Mitglied hinzufügen</a>
        </div>
      {/if}

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

                {#if canMutate && pendingMemberRemoval == member.sub}
                  <form method="POST" action="?/removeMember" class="workspace-inline-actions">
                    <input name="student_sub" type="hidden" value={member.sub} />
                    <button class="workspace-text-button workspace-text-button--danger" type="submit">Entfernen bestätigen</button>
                    <button class="workspace-text-button" type="button" onclick={() => (pendingMemberRemoval = null)}>Abbrechen</button>
                  </form>
                {:else if canMutate}
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
  </WorkspaceDrawer>
{/if}

{#if addMemberDialogOpen && canMutate}
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

{#if addUnitDialogOpen && canMutate}
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
