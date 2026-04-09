<script lang="ts">
  import { goto } from "$app/navigation";
  import LearningSubmissionArtifactView from "$lib/components/learning-unit/LearningSubmissionArtifactView.svelte";
  import type { LearningSubmission } from "$lib/types/learning";
  import type { LiveDetailSubmission } from "$lib/types/home";
  import { buildSubmissionArtifactView } from "$lib/utils/submission-artifacts";
  import { renderMarkdown } from "$lib/utils/markdown";
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

  function stripSubmissionSchemaHeader(value: string | null | undefined): string {
    const raw = typeof value === "string" ? value : "";
    return raw
      .replace(/^# scratch\.evidence\.v2\s*\n+/u, "")
      .replace(/^# makecode\.evidence\.v1\s*\n+/u, "");
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
        submission.files?.map((file) => ({
          mime_type: file.mime,
          size_bytes: file.size,
          url: file.url,
          download_url: file.url,
        })) ?? [],
    };
  }

  function primaryFile(submission: LiveDetailSubmission | null | undefined) {
    return submission?.files?.[0] ?? null;
  }

  let unitsLoading = $state(false);
  let activePanelTab = $state<PanelTab>("submission");

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

  $effect(() => {
    if (data.courseUnits) {
      unitsLoading = false;
    }
  });

  $effect(() => {
    data.selectedTaskId;
    activePanelTab = "submission";
  });
</script>

<svelte:head>
  <title>Live | GUSTAV</title>
</svelte:head>

<div class="workspace-page live-page">
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

  {#if data.dashboard}
    <section class="workspace-section live-kpi-section">
      <div class="live-summary-grid">
        <article class="live-summary-card">
          <span>Lernende</span>
          <strong>{data.dashboard.summary.learners_count}</strong>
        </article>
        <article class="live-summary-card">
          <span>Aufgaben</span>
          <strong>{data.dashboard.summary.tasks_count}</strong>
        </article>
        <article class="live-summary-card">
          <span>Bearbeitet</span>
          <strong>{data.dashboard.summary.completion_rate_percent}%</strong>
        </article>
        <article class="live-summary-card">
          <span>Ø Bewertung</span>
          <strong>{formatScore(data.dashboard.summary.average_score)}</strong>
        </article>
      </div>
    </section>

    <section class="workspace-panel workspace-section">
      <div class="workspace-section-header">
        <div class="workspace-section-heading">
          <p class="workspace-label">Klassenübersicht</p>
          <h3>Lernstand in der gewählten Lerneinheit</h3>
          <p class="workspace-note">
            Fortschritt, Durchschnitt und letzte Abgabe bleiben in der gemeinsamen Arbeitsfläche sichtbar.
          </p>
        </div>
      </div>

      <div class="live-dashboard">
        <div class="workspace-data-table-wrap">
          <table class="workspace-data-table">
            <thead>
              <tr>
                <th>Schüler</th>
                <th>Bearbeitet</th>
                <th>Ø Bewertung</th>
                <th>Letzte Abgabe</th>
              </tr>
            </thead>
            <tbody>
              {#each data.dashboard.rows as row}
                <tr class:is-selected={data.selectedStudentSub === row.student.sub}>
                  <td><a href={row.href}>{row.student.name}</a></td>
                  <td>{row.progress_percent}%</td>
                  <td>{formatScore(row.average_score)}</td>
                  <td>
                    {#if row.latest_submission}
                      <a href={row.href} class="live-latest-link">
                        <strong>{row.latest_submission.task_label}</strong>
                        <span>{formatScore(row.latest_submission.average_score)}</span>
                        <span>{row.latest_submission.created_at}</span>
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

        <aside class="workspace-panel live-panel" aria-label="Schülerdetail">
          {#if data.dashboard.selected_student_panel}
            <header class="live-panel__header">
              <div class="live-panel__copy">
                <h3>{data.dashboard.selected_student_panel.student.name}</h3>
              </div>
            </header>

            <nav class="live-task-strip" aria-label="Aufgaben der Lerneinheit">
              {#each data.dashboard.selected_student_panel.tasks as task}
                <a
                  href={task.href}
                  class={`live-task-strip__item live-task-strip__item--${taskStripTone(task.average_score, task.has_submission)}`}
                  class:is-active={data.dashboard.selected_student_panel.selected_task_id === task.task_id}
                  class:is-latest={task.is_latest_submission}
                  aria-label={`${task.task_label}: ${task.has_submission ? formatScore(task.average_score) : "Noch offen"}`}
                  title={`${task.task_label}: ${task.has_submission ? formatScore(task.average_score) : "Noch offen"}`}
                >
                </a>
              {/each}
            </nav>

            {#if data.dashboard.selected_student_panel.selected_task_detail}
              {@const selectedSubmission = data.dashboard.selected_student_panel.selected_task_detail}
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
  .live-panel {
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
  .live-panel {
    padding: var(--space-4);
    background: var(--color-bg-surface, #fff);
  }

  .live-summary-card strong {
    display: block;
    margin-top: var(--space-2);
    font-size: 1.25rem;
  }

  .live-dashboard {
    display: grid;
    grid-template-columns:
      minmax(34rem, 1.9fr)
      minmax(clamp(20rem, 30vw, 24rem), clamp(26rem, 33vw, 32rem));
    gap: clamp(0.9rem, 1.4vw, 1.4rem);
    align-items: start;
  }

  .live-latest-link {
    color: inherit;
    text-decoration: none;
    display: grid;
    gap: var(--space-1);
  }

  .live-panel {
    display: grid;
    gap: var(--space-4);
    position: sticky;
    top: calc(var(--space-5) + 4rem);
  }

  .live-panel__header,
  .live-panel-empty,
  .live-panel-block {
    display: grid;
    gap: var(--space-2);
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

  .live-panel-summary {
    border: 1px solid var(--color-line, rgba(27, 27, 27, 0.14));
  }

  .live-panel-summary__tabs {
    margin-top: var(--space-2);
  }

  .live-panel-summary__panel {
    display: grid;
    gap: var(--space-4);
  }

  @media (max-width: 960px) {
    .live-summary-grid,
    .live-dashboard,
    .live-selection__stack {
      grid-template-columns: 1fr;
    }

    .live-panel {
      position: static;
    }
  }
</style>
