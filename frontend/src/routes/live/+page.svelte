<script lang="ts">
  import { browser } from "$app/environment";
  import { goto } from "$app/navigation";
  import LearningSubmissionArtifactView from "$lib/components/learning-unit/LearningSubmissionArtifactView.svelte";
  import type { LearningSubmission } from "$lib/types/learning";
  import type { LiveDetailSubmission, LiveSummaryPayload, LiveUnitDashboardRow, LiveUnitDashboardView } from "$lib/types/home";
  import { buildSubmissionArtifactView } from "$lib/utils/submission-artifacts";
  import { handleBrowserAuthRecovery } from "$lib/utils/browser-auth-recovery";
  import { renderMarkdown } from "$lib/utils/markdown";
  import {
    buildDashboardViewModel,
    buildLiveDeltaPath,
    buildLiveDetailSheetPath,
    buildLivePageHref,
    buildLiveSummaryPath,
    createLiveWorkspaceController,
    navigateWithLiveSelectionFallback,
    type SortDirection,
    type SortKey
  } from "./page-state";
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();

  type PanelTab = "submission" | "evaluation" | "feedback";

  const formatScore = (value: number | null | undefined) =>
    typeof value === "number" ? `Ø ${value.toFixed(1)}` : "Noch unbewertet";

  const submissionTimestampFormatter = new Intl.DateTimeFormat("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Berlin",
  });

  const tabLabel = (tab: PanelTab) => {
    if (tab === "submission") {
      return "Abgabe";
    }
    if (tab === "evaluation") {
      return "Auswertung";
    }
    return "Rückmeldung";
  };

  function formatSubmissionTimestamp(value: string): string {
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return value;
    }
    const parts = submissionTimestampFormatter.formatToParts(parsed);
    const get = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value ?? "";
    return `${get("day")}.${get("month")}.${get("year")}, ab ${get("hour")}:${get("minute")} Uhr`;
  }

  function formatSubmissionDate(value: string): string {
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return value;
    }
    return new Intl.DateTimeFormat("de-DE", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      timeZone: "Europe/Berlin",
    }).format(parsed);
  }

  function stripSubmissionSchemaHeader(value: string | null | undefined): string {
    const raw = typeof value === "string" ? value : "";
    return raw
      .replace(/^\uFEFF/u, "")
      .replace(/^\s*# scratch\.evidence\.v2\s*\r?\n+/u, "")
      .replace(/^\s*# makecode\.evidence\.v1\s*\r?\n+/u, "")
      .replace(/^\s*# filius\.evidence\.v1\s*\r?\n+/u, "")
      .trimStart();
  }

  function isSubmissionSchemaPayload(value: string | null | undefined): boolean {
    const raw = typeof value === "string" ? value.replace(/^\uFEFF/u, "").trimStart() : "";
    return (
      raw.startsWith("# scratch.evidence.v2") ||
      raw.startsWith("# makecode.evidence.v1") ||
      raw.startsWith("# filius.evidence.v1")
    );
  }

  function taskStripTone(score: number | null, hasSubmission: boolean): string {
    if (!hasSubmission) {
      return "empty";
    }
    if (typeof score !== "number") {
      return "submitted-unscored";
    }
    if (score <= 0) {
      return "score-zero";
    }
    if (score >= 8) {
      return "score-high";
    }
    if (score >= 4) {
      return "score-mid";
    }
    return "score-low";
  }

  function detailToLearningSubmission(submission: LiveDetailSubmission): LearningSubmission {
    const primaryFile = submission.files?.[0];
    return {
      intent: "submit",
      id: submission.id,
      attempt_nr: 1,
      kind: submission.kind === "pdf" ? "file" : (submission.kind as LearningSubmission["kind"]),
      created_at: submission.created_at,
      analysis_status:
        submission.analysis_json || submission.feedback_md ? "completed" : submission.text_body || submission.files?.length ? "extracted" : "pending",
      text_body: submission.text_body ?? null,
      mime_type: primaryFile?.mime ?? null,
      score_raw: submission.score_raw ?? null,
      score_max: submission.score_max ?? null,
      feedback_md: submission.feedback_md ?? null,
      analysis_json: submission.analysis_json
        ? {
            schema: submission.analysis_json.schema,
            score: submission.analysis_json.score ?? null,
            text: submission.analysis_json.text ?? null,
            criteria_results: submission.analysis_json.criteria_results?.map((criterion) => ({
              criterion: criterion.criterion,
              score: criterion.score ?? null,
              max_score: criterion.max_score ?? null,
              explanation_md: criterion.explanation_md ?? null,
            })),
          }
        : null,
      files:
        submission.files?.flatMap((file) => {
          if (typeof file.mime !== "string" || typeof file.size !== "number" || typeof file.url !== "string") {
            return [];
          }
          return [{
            mime: file.mime,
            size: file.size,
            url: file.url,
            download_url: file.url,
          }];
        }) ?? [],
    };
  }

  function primaryFile(submission: LiveDetailSubmission | null | undefined) {
    return submission?.files?.[0] ?? null;
  }

  function defaultRowSort(left: LiveUnitDashboardRow, right: LiveUnitDashboardRow): number {
    return left.student.name.localeCompare(right.student.name, "de-DE", { sensitivity: "base" });
  }

  function compareNullableNumbers(left: number | null | undefined, right: number | null | undefined, direction: SortDirection): number {
    const leftMissing = typeof left !== "number";
    const rightMissing = typeof right !== "number";
    if (leftMissing && rightMissing) {
      return 0;
    }
    if (leftMissing) {
      return 1;
    }
    if (rightMissing) {
      return -1;
    }
    return direction === "asc" ? left - right : right - left;
  }

  function compareNullableDates(left: string | null | undefined, right: string | null | undefined, direction: SortDirection): number {
    const leftMs = left ? new Date(left).getTime() : Number.NaN;
    const rightMs = right ? new Date(right).getTime() : Number.NaN;
    const leftMissing = Number.isNaN(leftMs);
    const rightMissing = Number.isNaN(rightMs);
    if (leftMissing && rightMissing) {
      return 0;
    }
    if (leftMissing) {
      return 1;
    }
    if (rightMissing) {
      return -1;
    }
    return direction === "asc" ? leftMs - rightMs : rightMs - leftMs;
  }

  async function fetchSummaryState(args: {
    courseId: string | null;
    unitId: string | null;
  }): Promise<LiveSummaryPayload> {
    const href = buildLiveSummaryPath(args);
    if (!href) {
      throw new Error("live_summary_selection_incomplete");
    }
    const response = await fetch(href, {
      cache: "no-store",
      credentials: "include",
    });
    if (handleBrowserAuthRecovery(response)) {
      throw new Error("auth_recovery_started");
    }
    if (!response.ok) {
      throw new Error(`live_summary_fetch_failed_${response.status}`);
    }
    return (await response.json()) as LiveSummaryPayload;
  }

  async function fetchDetailState(selection: {
    courseId: string | null;
    unitId: string | null;
    studentSub: string | null;
    taskId: string | null;
  }): Promise<LiveDetailSubmission | null> {
    if (!selection.courseId || !selection.unitId || !selection.studentSub || !selection.taskId) {
      return null;
    }
    const response = await fetch(
      buildLiveDetailSheetPath({
        courseId: selection.courseId,
        unitId: selection.unitId,
        studentSub: selection.studentSub,
        taskId: selection.taskId
      }),
      {
        cache: "no-store",
        credentials: "include",
      }
    );
    if (handleBrowserAuthRecovery(response)) {
      throw new Error("auth_recovery_started");
    }
    if (!response.ok) {
      throw new Error(`live_detail_fetch_failed_${response.status}`);
    }
    const payload = (await response.json()) as { submission?: LiveDetailSubmission | null };
    return payload.submission ?? null;
  }

  async function fetchLiveDeltaState(args: { courseId: string; unitId: string; cursor: string }) {
    const response = await fetch(buildLiveDeltaPath(args), {
      cache: "no-store",
      credentials: "include",
    });
    if (response.status === 204) {
      return { status: 204 as const };
    }
    if (handleBrowserAuthRecovery(response)) {
      throw new Error("auth_recovery_started");
    }
    if (!response.ok) {
      throw new Error(`live_delta_fetch_failed_${response.status}`);
    }
    const payload = (await response.json()) as {
      cells?: Array<{ student_sub?: string | null; task_id?: string | null; changed_at?: string | null }>;
    };
    const cursor = (payload.cells ?? []).reduce((latest, cell) => {
      const changedAt = String(cell?.changed_at ?? "");
      return changedAt > latest ? changedAt : latest;
    }, args.cursor);
    return { status: 200 as const, cursor, cells: payload.cells ?? [] };
  }

  const workspaceController = createLiveWorkspaceController({
    initialSummary: null,
    initialDetail: null,
    initialSelection: {
      courseId: null,
      unitId: null,
      studentSub: null,
      taskId: null,
    },
    initialCursor: null,
    syncHref: (href: string) => {
      if (!browser) {
        return;
      }
      window.history.replaceState(window.history.state, "", href);
    },
    fetchSummary: fetchSummaryState,
    fetchDetail: fetchDetailState,
    fetchDelta: fetchLiveDeltaState,
  });

  let summaryState = $state<LiveSummaryPayload | null>(null);
  let detailState = $state<LiveDetailSubmission | null>(null);
  let unitsLoading = $state(false);
  let selectedStudentSubState = $state<string | null>(null);
  let selectedTaskIdState = $state<string | null>(null);
  let liveCursor = $state<string | null>(null);
  let activePanelTab = $state<PanelTab>("submission");
  let activeSortKey = $state<SortKey | null>(null);
  let activeSortDirection = $state<SortDirection | null>(null);

  function syncWorkspaceState(): void {
    const state = workspaceController.getState();
    summaryState = state.summary;
    detailState = state.detail;
    selectedStudentSubState = state.studentSub;
    selectedTaskIdState = state.taskId;
    activeSortKey = state.activeSortKey;
    activeSortDirection = state.activeSortDirection;
    liveCursor = state.cursor;
  }

  const courseRef = $derived.by(() => {
    const selectedCourse = data.courses.find((course) => course.id === data.selectedCourseId) ?? null;
    return {
      id: data.selectedCourseId ?? "",
      title: data.courseUnits?.course.title ?? selectedCourse?.title ?? "",
      href: data.selectedCourseId ? `/live?course_id=${data.selectedCourseId}` : "/live"
    };
  });

  const unitRef = $derived.by(() => {
    const selectedUnit = data.courseUnits?.units.find((unit) => unit.id === data.selectedUnitId) ?? null;
    return {
      id: data.selectedUnitId ?? "",
      title: selectedUnit?.title ?? "",
      position: selectedUnit?.position ?? 0,
      href:
        data.selectedCourseId && data.selectedUnitId
          ? `/live?course_id=${data.selectedCourseId}&unit_id=${data.selectedUnitId}`
          : "/live"
    };
  });

  const dashboardState = $derived.by(() =>
    buildDashboardViewModel({
      summary: summaryState,
      selection: {
        courseId: data.selectedCourseId ?? null,
        unitId: data.selectedUnitId ?? null,
        studentSub: selectedStudentSubState,
        taskId: selectedTaskIdState
      },
      detail: detailState,
      course: courseRef,
      unit: unitRef,
      user: data.detail?.user ?? {
        sub: "",
        name: "",
        role: "teacher",
        roles: ["teacher"]
      }
    })
  );

  const sortedRows = $derived.by(() => {
    const rows = [...(dashboardState?.rows ?? [])];
    rows.sort((left, right) => {
      if (!activeSortKey || !activeSortDirection) {
        return defaultRowSort(left, right);
      }
      if (activeSortKey === "student") {
        const compare = activeSortDirection === "asc"
          ? left.student.name.localeCompare(right.student.name, "de-DE", { sensitivity: "base" })
          : right.student.name.localeCompare(left.student.name, "de-DE", { sensitivity: "base" });
        return compare || defaultRowSort(left, right);
      }
      if (activeSortKey === "progress") {
        return compareNullableNumbers(left.progress_percent, right.progress_percent, activeSortDirection) || defaultRowSort(left, right);
      }
      if (activeSortKey === "average") {
        return compareNullableNumbers(left.average_score, right.average_score, activeSortDirection) || defaultRowSort(left, right);
      }
      return (
        compareNullableDates(left.latest_submission?.created_at, right.latest_submission?.created_at, activeSortDirection)
        || defaultRowSort(left, right)
      );
    });
    return rows;
  });

  function toggleSort(key: SortKey): void {
    workspaceController.toggleSort(key);
    syncWorkspaceState();
  }

  function ariaSortFor(key: SortKey): "ascending" | "descending" | "none" {
    if (activeSortKey !== key || !activeSortDirection) {
      return "none";
    }
    return activeSortDirection === "asc" ? "ascending" : "descending";
  }

  async function updateCourse(nextCourseId: string): Promise<void> {
    unitsLoading = Boolean(nextCourseId);

    const params = new URLSearchParams();
    if (nextCourseId) {
      params.set("course_id", nextCourseId);
    }

    await goto(`/live${params.size ? `?${params.toString()}` : ""}`, {
      keepFocus: true,
      noScroll: true,
      replaceState: true,
    });
  }

  async function updateUnit(nextUnitId: string): Promise<void> {
    if (!data.selectedCourseId) {
      return;
    }

    const params = new URLSearchParams();
    params.set("course_id", data.selectedCourseId);
    if (nextUnitId) {
      params.set("unit_id", nextUnitId);
    }

    await goto(`/live?${params.toString()}`, {
      keepFocus: true,
      noScroll: true,
      replaceState: true,
    });
  }

  async function openStudent(studentSub: string, event: MouseEvent): Promise<void> {
    event.preventDefault();
    const dashboard = dashboardState;
    const row = dashboard?.rows.find((entry) => entry.student.sub === studentSub) ?? null;
    await navigateWithLiveSelectionFallback({
      href: row?.href ?? buildLivePageHref({
        courseId: data.selectedCourseId ?? null,
        unitId: data.selectedUnitId ?? null,
        studentSub,
        taskId: null
      }),
      trySelect: async () => {
        await workspaceController.selectStudent(studentSub);
        syncWorkspaceState();
      },
      goto
    });
  }

  async function openTask(taskId: string, event: MouseEvent): Promise<void> {
    event.preventDefault();
    const taskHref = dashboardState?.selected_student_panel?.tasks.find((entry) => entry.task_id === taskId)?.href
      ?? buildLivePageHref({
        courseId: data.selectedCourseId ?? null,
        unitId: data.selectedUnitId ?? null,
        studentSub: selectedStudentSubState,
        taskId
      });
    await navigateWithLiveSelectionFallback({
      href: taskHref,
      trySelect: async () => {
        await workspaceController.selectTask(taskId);
        syncWorkspaceState();
      },
      goto
    });
  }

  $effect(() => {
    if (data.courseUnits) {
      unitsLoading = false;
    }
  });

  $effect(() => {
    workspaceController.resetFromServer({
      summary: data.summary,
      detail: data.detail?.submission ?? null,
      selection: {
        courseId: data.selectedCourseId ?? null,
        unitId: data.selectedUnitId ?? null,
        studentSub: data.selectedStudentSub ?? null,
        taskId: data.selectedTaskId ?? null,
      },
      cursor: data.liveCursorSeed ?? null,
    });
    syncWorkspaceState();
  });

  $effect(() => {
    selectedTaskIdState;
    activePanelTab = "submission";
  });

  $effect(() => {
    if (!browser || !data.selectedCourseId || !data.selectedUnitId) {
      return;
    }
    const intervalSeconds = Math.min(60, Math.max(1, Number(data.livePollIntervalSeconds ?? 3)));
    let cancelled = false;
    let inFlight = false;
    const timer = window.setInterval(async () => {
      if (cancelled || inFlight) {
        return;
      }
      inFlight = true;
      try {
        const reloaded = await workspaceController.poll();
        if (!cancelled && reloaded) {
          syncWorkspaceState();
        }
      } catch {
        // Keep the current workspace stable when one poll fails.
      } finally {
        inFlight = false;
      }
    }, intervalSeconds * 1000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  });
</script>

<svelte:head>
  <title>Live | GUSTAV</title>
</svelte:head>

<div class="workspace-page live-page">
  <div class="live-page__intro">
    <section class="workspace-panel workspace-panel--plain workspace-section live-selection-bar">
      {#if data.courses.length}
        <div class="live-selection__stack">
          <label class="live-selection__field">
            <span>Kurs</span>
            <select
              name="course_id"
              onchange={(event) => void updateCourse((event.currentTarget as HTMLSelectElement).value)}
            >
              <option value="">Kurs wählen</option>
              {#each data.courses as course}
                <option value={course.id} selected={data.selectedCourseId === course.id}>{course.title}</option>
              {/each}
            </select>
          </label>

          {#if data.selectedCourseId}
            <label class="live-selection__field">
              <span>Lerneinheit</span>
              <select
                name="unit_id"
                disabled={unitsLoading || !data.courseUnits?.units?.length}
                onchange={(event) => void updateUnit((event.currentTarget as HTMLSelectElement).value)}
              >
                {#if unitsLoading}
                  <option value="">Lerneinheiten werden geladen...</option>
                {:else if !data.courseUnits?.units?.length}
                  <option value="">Keine Lerneinheiten verfügbar</option>
                {:else}
                  <option value="">Lerneinheit wählen</option>
                  {#each data.courseUnits.units as unit}
                    <option value={unit.id} selected={data.selectedUnitId === unit.id}>
                      {unit.position}. {unit.title}
                    </option>
                  {/each}
                {/if}
              </select>
            </label>
          {/if}
        </div>
      {:else}
        <p class="workspace-empty">Noch keine Kurse für den Live-Raum verfügbar.</p>
      {/if}
    </section>

    {#if dashboardState}
      <section class="workspace-section live-kpi-section">
        <div class="live-summary-grid">
          <article class="live-summary-card">
            <span>Lernende</span>
            <strong>{dashboardState.summary.learners_count}</strong>
          </article>
          <article class="live-summary-card">
            <span>Aufgaben</span>
            <strong>{dashboardState.summary.tasks_count}</strong>
          </article>
          <article class="live-summary-card">
            <span>Bearbeitet</span>
            <strong>{dashboardState.summary.completion_rate_percent}%</strong>
          </article>
          <article class="live-summary-card">
            <span>Ø Bewertung</span>
            <strong>{formatScore(dashboardState.summary.average_score)}</strong>
          </article>
        </div>
      </section>
    {/if}
  </div>

  {#if dashboardState}
    <section class="live-page__workspace" aria-label="Live-Arbeitsbereich">
      <div class="live-workspace">
        <section class="workspace-panel workspace-section live-table-panel">
          <div class="workspace-section-header">
            <div class="workspace-section-heading">
              <p class="workspace-label">Klassenübersicht</p>
              <h3>Lernstand in der gewählten Lerneinheit</h3>
              <p class="workspace-note">
                Fortschritt, Durchschnitt und letzte Abgabe bleiben in der gemeinsamen Arbeitsfläche sichtbar.
              </p>
            </div>
          </div>

          <div class="workspace-data-table-wrap">
          <table class="workspace-data-table">
            <thead>
              <tr>
                <th aria-sort={ariaSortFor("student")}>
                  <button class="live-sort-button" type="button" onclick={() => toggleSort("student")}>Schüler</button>
                </th>
                <th aria-sort={ariaSortFor("progress")}>
                  <button class="live-sort-button" type="button" onclick={() => toggleSort("progress")}>Bearbeitet</button>
                </th>
                <th aria-sort={ariaSortFor("average")}>
                  <button class="live-sort-button" type="button" onclick={() => toggleSort("average")}>Ø Bewertung</button>
                </th>
                <th aria-sort={ariaSortFor("latest")}>
                  <button class="live-sort-button" type="button" onclick={() => toggleSort("latest")}>Letzte Abgabe</button>
                </th>
              </tr>
            </thead>
            <tbody>
              {#each sortedRows as row}
                <tr class:is-selected={selectedStudentSubState === row.student.sub}>
                  <td><a href={row.href} onclick={(event) => void openStudent(row.student.sub, event)}>{row.student.name}</a></td>
                  <td>{row.progress_percent}%</td>
                  <td>{formatScore(row.average_score)}</td>
                  <td>
                    {#if row.latest_submission}
                      <a href={row.href} class="live-latest-link" onclick={(event) => void openStudent(row.student.sub, event)}>
                        <span class="live-latest-link__date">{formatSubmissionDate(row.latest_submission.created_at)}</span>
                        <span class="live-latest-link__score">{formatScore(row.latest_submission.average_score)}</span>
                      </a>
                    {:else}
                      <span class="workspace-empty">Noch keine Abgabe</span>
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
          </div>
        </section>

        <aside class="workspace-panel live-panel" aria-label="Schülerdetail">
          {#if dashboardState.selected_student_panel}
            <header class="live-panel__header">
              <div class="live-panel__copy">
                <h3>{dashboardState.selected_student_panel.student.name}</h3>
              </div>
            </header>

            <nav class="live-task-strip" aria-label="Aufgaben der Lerneinheit">
              {#each dashboardState.selected_student_panel.tasks as task}
                <a
                  href={task.href}
                  class={`live-task-strip__item live-task-strip__item--${taskStripTone(task.average_score, task.has_submission)}`}
                  class:is-active={selectedTaskIdState === task.task_id}
                  class:is-latest={task.is_latest_submission}
                  aria-label={`${task.task_label}: ${task.has_submission ? formatScore(task.average_score) : "Noch offen"}`}
                  title={`${task.task_label}: ${task.has_submission ? formatScore(task.average_score) : "Noch offen"}`}
                  onclick={(event) => void openTask(task.task_id, event)}
                >
                </a>
              {/each}
            </nav>

            {#if dashboardState.selected_student_panel.selected_task_detail}
              {@const selectedSubmission = dashboardState.selected_student_panel.selected_task_detail}
              {@const selectedFile = primaryFile(selectedSubmission)}
              {@const artifactSubmission = detailToLearningSubmission(selectedSubmission)}
              {@const selectedArtifact = buildSubmissionArtifactView(artifactSubmission)}

              <section class="learning-task-submission-summary live-panel-summary" aria-label="Aufgabendetail">
                <header class="learning-task-submission-summary__header">
                  <div class="learning-task-submission-summary__copy">
                    <p class="learning-task-submission-summary__meta live-panel-summary__meta">
                      {formatSubmissionTimestamp(selectedSubmission.created_at)}
                    </p>
                    <div class="markdown-prose live-panel-summary__instruction">
                      {@html renderMarkdown(selectedSubmission.instruction_md)}
                    </div>
                  </div>
                </header>

                <div class="learning-task-submission-summary__tabs live-panel-summary__tabs" role="tablist" aria-label="Schülerdetail">
                  <button
                    class="workspace-tab"
                    class:workspace-tab--active={activePanelTab === "submission"}
                    role="tab"
                    type="button"
                    aria-selected={activePanelTab === "submission"}
                    onclick={() => (activePanelTab = "submission")}
                  >
                    Abgabe
                  </button>
                  <button
                    class="workspace-tab"
                    class:workspace-tab--active={activePanelTab === "feedback"}
                    role="tab"
                    type="button"
                    aria-selected={activePanelTab === "feedback"}
                    onclick={() => (activePanelTab = "feedback")}
                  >
                    Rückmeldung
                  </button>
                  <button
                    class="workspace-tab"
                    class:workspace-tab--active={activePanelTab === "evaluation"}
                    role="tab"
                    type="button"
                    aria-selected={activePanelTab === "evaluation"}
                    onclick={() => (activePanelTab = "evaluation")}
                  >
                    Auswertung
                  </button>
                </div>

                <div class="learning-task-submission-summary__panel live-panel-summary__panel" role="tabpanel" aria-label={tabLabel(activePanelTab)}>
                  {#if activePanelTab === "submission"}
                    <section class="live-panel-block">
                      <p class="workspace-label">Abgabe</p>
                      {#if selectedArtifact}
                        <LearningSubmissionArtifactView submission={artifactSubmission} />
                      {:else if isSubmissionSchemaPayload(selectedSubmission.text_body)}
                        <pre class="learning-task-submission-summary__plain">{stripSubmissionSchemaHeader(selectedSubmission.text_body)}</pre>
                      {:else if selectedSubmission.text_body}
                        <div class="markdown-prose">
                          {@html renderMarkdown(stripSubmissionSchemaHeader(selectedSubmission.text_body))}
                        </div>
                      {:else if selectedFile?.mime?.startsWith("image/")}
                        <div class="learning-task-submission-summary__asset">
                          <img alt="Abgabevorschau" class="learning-task-submission-summary__image" src={selectedFile.url} />
                          <p class="learning-task-submission-summary__asset-meta">{selectedFile.mime}</p>
                          <a class="workspace-link-action" href={selectedFile.url}>Datei öffnen</a>
                        </div>
                      {:else if selectedFile?.mime === "application/pdf"}
                        <div class="learning-task-submission-summary__asset">
                          <iframe class="learning-task-submission-summary__frame" src={selectedFile.url} title={`Abgabe ${selectedSubmission.created_at}`}></iframe>
                          <p class="learning-task-submission-summary__asset-meta">{selectedFile.mime}</p>
                          <a class="workspace-link-action" href={selectedFile.url}>Datei öffnen</a>
                        </div>
                      {:else if selectedFile?.url}
                        <div class="learning-task-submission-summary__asset">
                          <p class="learning-task-submission-summary__plain">{selectedFile.mime ?? "Datei"}</p>
                          <a class="workspace-link-action" href={selectedFile.url}>Datei öffnen</a>
                        </div>
                      {:else}
                        <p class="learning-task-submission-summary__plain">Keine Vorschau für diese Abgabe verfügbar.</p>
                        <p class="learning-task-submission-summary__plain">
                          Die Submission wurde erkannt, aber für diesen Typ steht hier aktuell keine direkt lesbare Darstellung bereit.
                        </p>
                      {/if}
                    </section>

                  {:else if activePanelTab === "feedback"}
                    <section class="live-panel-block">
                      <p class="workspace-label">Rückmeldung</p>
                      {#if selectedSubmission.feedback_md}
                        <div class="markdown-prose">
                          {@html renderMarkdown(selectedSubmission.feedback_md)}
                        </div>
                      {:else}
                        <p class="learning-task-submission-summary__plain">Es liegt noch keine Rückmeldung vor.</p>
                      {/if}
                    </section>
                  {:else}
                    <section class="live-panel-block">
                      <p class="workspace-label">Auswertung</p>
                      {#if selectedSubmission.analysis_json?.criteria_results?.length}
                        <ul class="learning-unit-criteria">
                          {#each selectedSubmission.analysis_json.criteria_results as criterion}
                            <li>
                              <strong>{criterion.criterion}</strong>
                              {#if criterion.score !== undefined && criterion.score !== null}
                                : {criterion.score}/{criterion.max_score ?? 10}
                              {/if}
                              {#if criterion.explanation_md}
                                <div class="markdown-prose">
                                  {@html renderMarkdown(criterion.explanation_md)}
                                </div>
                              {/if}
                            </li>
                          {/each}
                        </ul>
                      {:else if typeof selectedSubmission.score_raw === "number" && typeof selectedSubmission.score_max === "number"}
                        <p class="learning-task-submission-summary__plain">
                          Punktestand: {selectedSubmission.score_raw}/{selectedSubmission.score_max}
                        </p>
                      {:else}
                        <p class="learning-task-submission-summary__plain">Es liegt noch keine Auswertung vor.</p>
                      {/if}
                    </section>
                  {/if}
                </div>
              </section>
            {:else}
              <section class="live-panel-empty">
                <p class="workspace-label">Keine Abgabe</p>
                <p class="workspace-empty">
                  Für die gewählte Aufgabe liegt noch keine Abgabe vor. Die Aufgabenleiste bleibt zum schnellen Wechsel sichtbar.
                </p>
              </section>
            {/if}
          {:else}
            <section class="live-panel-empty">
              <p class="workspace-empty">
                Wähle eine Schülerzeile, um Aufgabenleiste und Detailansicht zu öffnen.
              </p>
            </section>
          {/if}
        </aside>
      </div>
    </section>
  {/if}
</div>

<style>
  .live-page {
    gap: 1.15rem;
  }

  .live-page__intro,
  .live-page__workspace {
    width: 100%;
    margin-inline: auto;
  }

  .live-page__intro {
    max-width: 112rem;
  }

  .live-page__workspace {
    max-width: 132rem;
  }

  .live-kpi-section {
    background: transparent;
    border: 0;
    box-shadow: none;
    padding: 0;
  }

  .live-selection-bar {
    padding: 0;
  }

  .live-selection__stack {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-3);
    width: 100%;
    align-items: end;
  }

  .live-selection__field {
    display: grid;
    gap: var(--space-2);
  }

  .live-selection__field span,
  .live-summary-card span {
    font-family: var(--font-mono, monospace);
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .live-selection__field select,
  .live-summary-card,
  .live-panel,
  .live-table-panel {
    border: 1px solid var(--color-border, #1b1b1b);
    border-radius: 0;
  }

  .live-selection__field select {
    min-height: 2.75rem;
    padding: 0 var(--space-3);
    background: var(--color-bg-surface, #fff);
    color: var(--color-text, #1a1c1c);
  }

  .live-summary-grid {
    display: grid;
    gap: var(--space-3);
    grid-template-columns: repeat(auto-fit, minmax(clamp(11rem, 22vw, 15rem), 1fr));
    margin-bottom: var(--space-5);
  }

  .live-summary-card,
  .live-panel,
  .live-table-panel {
    padding: var(--space-4);
    background: var(--color-bg-surface, #fff);
  }

  .live-summary-card strong {
    display: block;
    margin-top: var(--space-2);
    font-size: 1.25rem;
  }

  .live-workspace {
    display: grid;
    grid-template-columns:
      minmax(0, 2.35fr)
      minmax(22rem, 1fr);
    gap: clamp(1.2rem, 1.8vw, 1.8rem);
    align-items: start;
  }

  .live-latest-link {
    color: inherit;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .live-latest-link__date,
  .live-latest-link__score {
    white-space: nowrap;
  }

  .live-sort-button {
    border: 0;
    padding: 0;
    background: transparent;
    color: inherit;
    font: inherit;
    font-weight: inherit;
    cursor: pointer;
  }

  .live-table-panel {
    min-width: 0;
    background: color-mix(in srgb, var(--color-bg-surface, #fff) 97%, var(--color-border, #1b1b1b) 3%);
    box-shadow:
      0 0 0 1px color-mix(in srgb, var(--color-border, #1b1b1b) 24%, transparent 76%),
      0 18px 36px color-mix(in srgb, var(--color-shadow, rgba(0, 0, 0, 0.18)) 42%, transparent 58%);
  }

  .live-panel {
    display: grid;
    gap: var(--space-4);
    min-width: 0;
    position: sticky;
    top: calc(var(--space-5) + 4rem);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--color-bg-surface, #fff) 94%, var(--color-accent, #ff512f) 6%) 0%,
        var(--color-bg-surface, #fff) 18%
      );
    border-color: color-mix(in srgb, var(--color-accent, #ff512f) 24%, var(--color-border, #1b1b1b) 76%);
    box-shadow:
      0 0 0 1px color-mix(in srgb, var(--color-accent, #ff512f) 14%, transparent 86%),
      0 24px 44px color-mix(in srgb, var(--color-shadow, rgba(0, 0, 0, 0.18)) 52%, transparent 48%);
  }

  .live-panel__header,
  .live-panel-empty,
  .live-panel-block {
    display: grid;
    gap: var(--space-2);
  }

  .live-panel-block,
  .live-panel-summary,
  .live-panel-summary__panel {
    min-width: 0;
  }

  .live-panel__copy h3,
  .live-panel-summary__title {
    margin: 0;
  }

  .live-task-strip {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(0.7rem, 0.9rem));
    gap: 0.28rem;
    justify-content: start;
  }

  .live-task-strip__item {
    width: 0.85rem;
    min-height: 1.15rem;
    border: 1px solid color-mix(in srgb, var(--color-border, #1b1b1b) 72%, transparent 28%);
    text-decoration: none;
    color: inherit;
    display: block;
    padding: 0;
    transition:
      transform 120ms ease,
      background 120ms ease,
      border-color 120ms ease;
  }

  .live-task-strip__item:hover,
  .live-task-strip__item:focus-visible {
    transform: translateY(-1px);
  }

  .live-task-strip__item--empty {
    background: color-mix(in srgb, var(--color-bg-muted, #f3f3f4) 92%, white 8%);
    border-color: color-mix(in srgb, var(--color-border, #1b1b1b) 20%, transparent 80%);
  }

  .live-task-strip__item--submitted-unscored {
    background: color-mix(in srgb, var(--color-border, #1b1b1b) 72%, white 28%);
    border-color: color-mix(in srgb, var(--color-border, #1b1b1b) 84%, transparent 16%);
  }

  .live-task-strip__item--score-zero {
    background: #7a0000;
    border-color: #7a0000;
  }

  .live-task-strip__item--score-low {
    background: #c62828;
    border-color: #c62828;
  }

  .live-task-strip__item--score-mid {
    background: #d87a00;
    border-color: #d87a00;
  }

  .live-task-strip__item--score-high {
    background: #2f8f5b;
    border-color: #2f8f5b;
  }

  .live-task-strip__item.is-active {
    outline: 2px solid var(--color-accent, #ff512f);
    outline-offset: -2px;
  }

  .live-task-strip__item.is-latest::after {
    content: "";
    display: block;
    width: 100%;
    height: 2px;
    background: var(--color-accent, #ff512f);
    margin-top: calc(1.15rem - 2px);
  }

  :global(.dark) .live-task-strip__item--empty {
    background: #4a4f54;
    border-color: color-mix(in srgb, white 26%, transparent 74%);
  }

  :global(.dark) .live-task-strip__item--submitted-unscored {
    background: #7b8288;
    border-color: #7b8288;
  }

  :global(.dark) .live-task-strip__item--score-zero {
    background: #ff4d4d;
    border-color: #ff4d4d;
  }

  :global(.dark) .live-task-strip__item--score-low {
    background: #ff6b57;
    border-color: #ff6b57;
  }

  :global(.dark) .live-task-strip__item--score-mid {
    background: #ff9a2f;
    border-color: #ff9a2f;
  }

  :global(.dark) .live-task-strip__item--score-high {
    background: #49b36f;
    border-color: #49b36f;
  }

  :global(.dark) .live-table-panel {
    background: color-mix(in srgb, var(--color-bg-surface, #171717) 94%, white 6%);
  }

  :global(.dark) .live-panel {
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--color-bg-surface, #171717) 90%, var(--color-accent, #ff866b) 10%) 0%,
        var(--color-bg-surface, #171717) 18%
      );
    border-color: color-mix(in srgb, var(--color-accent, #ff866b) 24%, white 76%);
  }

  .live-panel-summary {
    border: 1px solid var(--color-line, rgba(27, 27, 27, 0.14));
  }

  .live-panel-summary__tabs {
    margin-top: var(--space-2);
  }

  .live-panel-summary__panel {
    display: grid;
    gap: var(--space-4);
    min-width: 0;
  }

  @media (max-width: 960px) {
    .live-summary-grid,
    .live-workspace,
    .live-selection__stack {
      grid-template-columns: 1fr;
    }

    .live-panel {
      position: static;
    }
  }
</style>
