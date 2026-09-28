<script lang="ts">
  import ChoiceSwitch from "$lib/components/ui/ChoiceSwitch.svelte";
  import type { LivePracticeCell } from "$lib/types/home";
  import type { LiveLearningCellView, LiveMatrixRowView } from "./live-matrix-view";

  type MatrixView = {
    learningGroups: Array<{ id: string; title: string; taskIds: string[] }>;
    practiceModules: Array<{ id: string; title: string; task_ids: string[] }>;
    rows: LiveMatrixRowView[];
  };

  let {
    view,
    activeView,
    selectedStudentSub,
    selectedTaskId,
    mobileLearningGroupId,
    mobilePracticeModuleId,
    onViewChange,
    onMobileLearningGroupChange,
    onMobilePracticeModuleChange,
    onOpenStudent,
    onOpenTask,
    onOpenPracticeModule
  }: {
    view: MatrixView;
    activeView: "learning" | "practice";
    selectedStudentSub: string | null;
    selectedTaskId: string | null;
    mobileLearningGroupId: string;
    mobilePracticeModuleId: string;
    onViewChange: (value: "learning" | "practice") => void;
    onMobileLearningGroupChange: (value: string) => void;
    onMobilePracticeModuleChange: (value: string) => void;
    onOpenStudent: (studentSub: string) => void;
    onOpenTask: (studentSub: string, taskId: string) => void;
    onOpenPracticeModule: (studentSub: string, moduleId: string, taskId: string | null) => void;
  } = $props();

  const practiceStatusLabel = (cell: LivePracticeCell | null): string => {
    if (!cell) return "Keine Daten";
    if (cell.status === "locked") return "Gesperrt";
    if (cell.status === "due") return "Fällig";
    if (cell.status === "insufficient") return "Noch nicht sicher";
    if (cell.status === "partial") return "Teilweise sicher";
    return "Sicher";
  };

  const learningAria = (row: LiveMatrixRowView, cell: LiveLearningCellView): string =>
    `${row.student.name}, ${cell.task.section_title || "Lernaufgabe"}, Aufgabe ${cell.task.position}: ${cell.label}`;

  const practiceAria = (row: LiveMatrixRowView, moduleTitle: string, cell: LivePracticeCell | null): string =>
    `${row.student.name}, Übungsmodul ${moduleTitle}: ${practiceStatusLabel(cell)}`;

  const learningSummaryAria = (row: LiveMatrixRowView): string => {
    const summary = row.learningSummary;
    const submitted = `${summary.completed} von ${summary.total} Lernaufgaben abgegeben`;
    if (summary.rated === 0) {
      return `${row.student.name}: ${submitted}; keine bewertete Lernaufgabe`;
    }
    const ratedTasks = summary.rated === 1
      ? "einer bewerteten Lernaufgabe"
      : `${summary.rated} bewerteten Lernaufgaben`;
    return `${row.student.name}: ${submitted}; Durchschnitt ${summary.averageLabel} aus ${ratedTasks}`;
  };
</script>

<section class="live-matrix" aria-labelledby="live-matrix-heading">
  <header class="live-matrix__header">
    <div class="live-matrix__heading">
      <h2 id="live-matrix-heading">Klassenübersicht</h2>
      <p class="live-matrix__meta">{view.rows.length} {view.rows.length === 1 ? "Person" : "Lernende"} · {view.learningGroups.reduce((count, group) => count + group.taskIds.length, 0)} Lernaufgaben</p>
    </div>
    <div class="live-matrix__switch"><ChoiceSwitch
      legend="Ansicht"
      legendHidden={true}
      name="live-matrix-view"
      value={activeView}
      options={[
        { value: "learning", label: "Aufgaben" },
        { value: "practice", label: "Üben", disabled: view.practiceModules.length === 0 }
      ]}
      onValueChange={(value) => onViewChange(value as "learning" | "practice")}
    /></div>
  </header>

  {#if view.rows.length === 0}
    <p class="workspace-empty">Noch keine Schüler im Kurs.</p>
  {/if}

  {#if activeView === "learning"}
    {#if view.learningGroups.length}
      <label class="live-matrix__mobile-select">
        <span>Modul</span>
        <select value={mobileLearningGroupId} onchange={(event) => onMobileLearningGroupChange(event.currentTarget.value)}>
          {#each view.learningGroups as group}
            <option value={group.id}>{group.title}</option>
          {/each}
        </select>
      </label>
      <!-- svelte-ignore a11y_no_noninteractive_tabindex (Scrollable labelled table region.) -->
      <div class="live-matrix__scroll" role="region" aria-label="Lernaufgaben nach Schülern" tabindex="0">
        <table
          style:--matrix-width={`${336 + view.learningGroups.reduce((count, group) => count + group.taskIds.length, 0) * 48}px`}
          style:--mobile-width={`${296 + (view.learningGroups.find((group) => group.id === mobileLearningGroupId)?.taskIds.length ?? 0) * 48}px`}
        >
          <colgroup>
            <col class="live-matrix__name-col" />
            {#each view.learningGroups as group}
              {#each group.taskIds as taskId}
                <col class="live-matrix__task-col" class:live-matrix__mobile-hidden={mobileLearningGroupId !== group.id} />
              {/each}
            {/each}
            <col class="live-matrix__learning-summary-col" />
            <col class="live-matrix__practice-summary-col" />
          </colgroup>
          <thead>
            <tr>
              <th class="live-matrix__name" rowspan="2">Schüler</th>
              {#each view.learningGroups as group}
                <th
                  class:live-matrix__mobile-hidden={mobileLearningGroupId !== group.id}
                  colspan={group.taskIds.length}
                  scope="colgroup"
                ><span class="live-matrix__module-title" title={group.title}>{group.title}</span></th>
              {/each}
              <th class="live-matrix__learning-summary" rowspan="2" scope="col">Stand</th>
              <th class="live-matrix__practice-summary" rowspan="2" scope="col">Üben</th>
            </tr>
            <tr>
              {#each view.learningGroups as group}
                {#each group.taskIds as taskId, taskIndex}
                  <th class:live-matrix__mobile-hidden={mobileLearningGroupId !== group.id} scope="col">{taskIndex + 1}</th>
                {/each}
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each view.rows as row}
              <tr class:is-selected={selectedStudentSub === row.student.sub}>
                <th class="live-matrix__name" scope="row">
                  <button type="button" onclick={() => onOpenStudent(row.student.sub)}>{row.student.name}</button>
                </th>
                {#each view.learningGroups as group}
                  {#each row.learningCells.filter((entry) => group.taskIds.includes(entry.task.id)) as learningCell}
                    <td class:live-matrix__mobile-hidden={mobileLearningGroupId !== group.id}>
                      <button
                        type="button"
                        class="live-score"
                        class:is-selected={selectedStudentSub === row.student.sub && selectedTaskId === learningCell.task.id}
                        data-tone={learningCell.tone}
                        aria-label={learningAria(row, learningCell)}
                        onclick={() => onOpenTask(row.student.sub, learningCell.task.id)}
                      >{learningCell.label}</button>
                    </td>
                  {/each}
                {/each}
                <td class="live-matrix__learning-summary" aria-label={learningSummaryAria(row)}>
                  <span class="live-learning-summary">
                    <strong>{row.learningSummary.completed}/{row.learningSummary.total}</strong>
                    <small data-tone={row.learningSummary.tone}>Ø {row.learningSummary.averageLabel}</small>
                  </span>
                </td>
                <td class="live-matrix__practice-summary">
                  <button
                    class="live-practice-counts"
                    type="button"
                    aria-label={`${row.student.name}: ${row.practiceSummary.due} neue oder fällige und ${row.practiceSummary.secure} sichere Übungsaufgaben`}
                    disabled={view.practiceModules.length === 0}
                    onclick={() => onOpenPracticeModule(row.student.sub, view.practiceModules[0]?.id ?? "", view.practiceModules[0]?.task_ids[0] ?? null)}
                  >
                    <span data-tone="due">● {row.practiceSummary.due}</span>
                    <span data-tone="secure">● {row.practiceSummary.secure}</span>
                  </button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {:else}
      <p class="workspace-empty">Diese Lerneinheit enthält noch keine Lernaufgaben.</p>
    {/if}
  {:else if view.practiceModules.length}
    <label class="live-matrix__mobile-select">
      <span>Übungsmodul</span>
      <select value={mobilePracticeModuleId} onchange={(event) => onMobilePracticeModuleChange(event.currentTarget.value)}>
        {#each view.practiceModules as module}
          <option value={module.id}>{module.title}</option>
        {/each}
      </select>
    </label>
    <!-- svelte-ignore a11y_no_noninteractive_tabindex (Scrollable labelled table region.) -->
    <div class="live-matrix__scroll" role="region" aria-label="Übungsmodule nach Schülern" tabindex="0">
      <table class="live-matrix__practice-table" style:--matrix-width={`${176 + view.practiceModules.length * 176}px`} style:--mobile-width="312px">
        <colgroup>
          <col class="live-matrix__name-col" />
          {#each view.practiceModules as module}
            <col class="live-matrix__practice-col" class:live-matrix__mobile-hidden={mobilePracticeModuleId !== module.id} />
          {/each}
        </colgroup>
        <thead>
          <tr>
            <th class="live-matrix__name">Schüler</th>
            {#each view.practiceModules as module}
              <th class:live-matrix__mobile-hidden={mobilePracticeModuleId !== module.id} scope="col">{module.title}</th>
            {/each}
          </tr>
        </thead>
        <tbody>
          {#each view.rows as row}
            <tr class:is-selected={selectedStudentSub === row.student.sub}>
              <th class="live-matrix__name" scope="row">
                <button type="button" onclick={() => onOpenStudent(row.student.sub)}>{row.student.name}</button>
              </th>
              {#each row.practiceCells as entry}
                <td class:live-matrix__mobile-hidden={mobilePracticeModuleId !== entry.module.id}>
                  <button
                    type="button"
                    class="live-practice-status"
                    data-status={entry.cell?.status ?? "empty"}
                    aria-label={practiceAria(row, entry.module.title, entry.cell)}
                    onclick={() => onOpenPracticeModule(row.student.sub, entry.module.id, entry.module.task_ids[0] ?? null)}
                  >
                    <strong>{practiceStatusLabel(entry.cell)}</strong>
                    {#if entry.cell && entry.cell.status !== "locked"}
                      <small>{entry.cell.due_tasks_count} fällig · {entry.cell.secure_tasks_count} sicher</small>
                    {/if}
                  </button>
                </td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else}
    <p class="workspace-empty">Diese Lerneinheit enthält noch keine Übungsmodule.</p>
  {/if}
</section>

<style>
  .live-matrix { min-width: 0; }
  .live-matrix__header { display: flex; justify-content: space-between; align-items: center; gap: var(--space-5); padding: var(--space-3) var(--space-5); }
  .live-matrix__heading { display: flex; align-items: baseline; flex-wrap: wrap; column-gap: var(--space-3); row-gap: var(--space-1); }
  .live-matrix__header h2 { margin: 0; font: 600 1.125rem var(--font-ui); }
  .live-matrix__meta { margin: 0; color: var(--color-text-muted); font-size: var(--font-size-xs); }
  .live-matrix__switch { flex: 0 0 9rem; }
  .live-matrix__scroll { max-width: 100%; overflow-x: auto; border-top: 1px solid var(--color-line); background: var(--color-bg-surface); }
  .live-matrix__scroll:focus-visible { outline: 2px solid var(--color-link); outline-offset: 2px; }
  table { width: var(--matrix-width); table-layout: fixed; border-collapse: collapse; }
  .live-matrix__name-col { width: 176px; }
  .live-matrix__task-col { width: 48px; }
  .live-matrix__learning-summary-col { width: 88px; }
  .live-matrix__practice-summary-col { width: 72px; }
  .live-matrix__practice-col { width: 176px; }
  .live-matrix__module-title { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; line-height: 1.35; }
  th, td { border-right: 1px solid var(--color-line); border-bottom: 1px solid var(--color-line); text-align: center; padding: 0; height: 2.9rem; }
  thead th { padding: var(--space-2); background: var(--color-bg-muted); font-family: var(--font-ui); font-size: var(--font-size-xs); font-weight: 500; white-space: normal; }
  tbody tr:last-child th, tbody tr:last-child td { border-bottom: 0; }
  tr.is-selected > .live-matrix__name { box-shadow: inset 3px 0 0 var(--color-accent); }
  .live-matrix__name { position: sticky; left: 0; z-index: 2; padding: 0 var(--space-4); text-align: left; background: var(--color-bg-surface); }
  thead .live-matrix__name { z-index: 4; background: var(--color-bg-muted); }
  .live-matrix__name button { width: 100%; overflow: hidden; border: 0; padding: 0; background: transparent; color: inherit; font: inherit; font-weight: 650; text-align: left; text-overflow: ellipsis; white-space: nowrap; cursor: pointer; }
  .live-score { display: block; box-sizing: border-box; width: 100%; min-height: 3rem; border: 0; border-bottom: 2px solid transparent; background: transparent; color: var(--color-text); font: 600 var(--font-size-sm) var(--font-ui); font-variant-numeric: tabular-nums; cursor: pointer; }
  .live-score[data-tone="high"] { border-bottom-color: var(--color-success); background: var(--color-success-soft); }
  .live-score[data-tone="mid"] { border-bottom-color: var(--color-warning); background: var(--color-warning-soft); }
  .live-score[data-tone="low"] { border-bottom-color: var(--color-danger); background: var(--color-danger-soft); }
  .live-score[data-tone="submitted"] { border-bottom-color: var(--color-info); background: var(--color-info-soft); }
  .live-score:hover, .live-score.is-selected, .live-practice-status:hover, .live-practice-counts:hover { outline: 2px solid var(--color-link); outline-offset: -2px; }
  .live-score:focus-visible, .live-practice-status:focus-visible, .live-practice-counts:focus-visible, .live-matrix__name button:focus-visible { outline: 2px solid var(--color-link); outline-offset: -2px; }
  .live-matrix__learning-summary { position: sticky; right: 4.5rem; z-index: 2; width: 5.5rem; min-width: 5.5rem; max-width: 5.5rem; padding: 0; background: var(--color-bg-surface); box-shadow: inset 1px 0 0 var(--color-line); text-align: center; }
  thead .live-matrix__learning-summary { z-index: 4; padding: var(--space-2) var(--space-1); background: var(--color-bg-muted); }
  .live-learning-summary { display: grid; min-height: 2.9rem; place-content: center; gap: var(--space-1); padding: var(--space-1) var(--space-2); font-variant-numeric: tabular-nums; line-height: 1; }
  .live-learning-summary strong { font: 700 var(--font-size-sm) var(--font-mono); }
  .live-learning-summary small { color: var(--color-text-muted); font: 600 var(--font-size-xs)/1.1 var(--font-mono); }
  .live-learning-summary small[data-tone="high"] { color: var(--color-success); }
  .live-learning-summary small[data-tone="mid"] { color: var(--color-warning); }
  .live-learning-summary small[data-tone="low"] { color: var(--color-danger); }
  .live-matrix__practice-summary { width: 4.5rem; min-width: 4.5rem; max-width: 4.5rem; position: sticky; right: 0; z-index: 2; background: var(--color-bg-surface); }
  thead .live-matrix__practice-summary { z-index: 4; background: var(--color-bg-muted); }
  .live-practice-counts { display: grid; grid-template-columns: 1fr 1fr; width: 100%; min-height: 2.9rem; align-items: center; gap: var(--space-1); border: 0; padding: 0 var(--space-1); background: transparent; font: 700 .78rem var(--font-mono); cursor: pointer; }
  .live-practice-counts [data-tone="due"] { color: var(--color-info); }
  .live-practice-counts [data-tone="secure"] { color: var(--color-success); }
  .live-practice-counts:disabled { cursor: default; opacity: .55; }
  .live-matrix__practice-table th:not(.live-matrix__name) { overflow-wrap: anywhere; }
  .live-practice-status { display: grid; place-content: center; gap: var(--space-1); width: 100%; min-height: 3.5rem; border: 0; border-left: 3px solid var(--color-line); padding: var(--space-2); background: transparent; color: inherit; cursor: pointer; }
  .live-practice-status strong { font-size: .86rem; }
  .live-practice-status small { color: var(--color-text-muted); white-space: nowrap; }
  .live-practice-status[data-status="due"] { border-left-color: var(--color-info); background: var(--color-info-soft); }
  .live-practice-status[data-status="secure"] { border-left-color: var(--color-success); background: var(--color-success-soft); }
  .live-practice-status[data-status="partial"] { border-left-color: var(--color-warning); background: var(--color-warning-soft); }
  .live-practice-status[data-status="insufficient"] { border-left-color: var(--color-danger); background: var(--color-danger-soft); }
  .live-matrix__mobile-select { display: none; }
  @media (max-width: 700px) {
    .live-matrix__header { padding: var(--space-3); gap: var(--space-2); }
    .live-matrix__header h2 { font-size: var(--font-size-base); }
    table { width: var(--mobile-width); }
    .live-matrix__name-col { width: 136px; }
    .live-matrix__mobile-select { display: grid; gap: var(--space-1); margin: 0 var(--space-3) var(--space-3); }
    .live-matrix__mobile-select span { font: .76rem var(--font-mono); text-transform: uppercase; }
    .live-matrix__mobile-select select { min-height: 2.75rem; border: 1px solid var(--color-border); border-radius: 0; padding: 0 var(--space-3); background: var(--color-bg-surface); color: var(--color-text); }
    .live-matrix__mobile-hidden { display: none; }
    .live-matrix__name { padding-inline: var(--space-3); }
    .live-score { min-height: var(--layout-control-min); }
  }
  @media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto; } }
</style>
