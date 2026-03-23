<script lang="ts">
  import H5PTaskPlayer from "$lib/components/H5PTaskPlayer.svelte";
  import type { LearningSection, LearningSubmission, LearningTask } from "$lib/types/learning";
  import type { ActionData, PageData } from "./$types";

  let { data, form }: { data: PageData; form: ActionData } = $props();

  function isHistoryOpen(taskId: string): boolean {
    return data.historyTaskId === taskId;
  }

  function historyHref(taskId: string): string {
    const params = new URLSearchParams();
    params.set("history", taskId);
    if (data.activeModule?.module.id) {
      params.set("module", data.activeModule.module.id);
    }
    return `?${params.toString()}#task-${taskId}`;
  }

  function moduleHref(moduleId: string): string {
    const params = new URLSearchParams();
    params.set("module", moduleId);
    return `?${params.toString()}`;
  }

  function uploadOnly(task: LearningTask): boolean {
    return task.kind === "visual" || task.kind === "scratch" || task.kind === "calliope";
  }

  function humanStatus(submission: LearningSubmission): string {
    if (submission.kind === "h5p" && submission.score_raw !== null && submission.score_raw !== undefined) {
      return `${submission.analysis_status} · ${submission.score_raw}/${submission.score_max ?? 0}`;
    }
    return submission.analysis_status;
  }
</script>

<svelte:head>
  <title>{data.selectedUnit?.unit.title ?? "Lernraum"} | GUSTAV</title>
</svelte:head>

<section class="workspace">
  <header class="hero">
    <div>
      <p class="kicker">Lernraum</p>
      <h2>{data.selectedUnit?.unit.title}</h2>
      <p class="lead">
        {#if data.selectedUnit?.unit.unit_type === "modular"}
          Modulare Einheit mit Graph, offenen Modulen und serverseitigen Abgaben.
        {:else}
          Lineare Einheit mit direkt sichtbaren Abschnitten und Aufgaben.
        {/if}
      </p>
    </div>

    <a class="back-link" href={`/learning/courses/${data.courseId}`}>Zurueck zum Kurs</a>
  </header>

  <nav class="unit-switcher" aria-label="Lerneinheiten">
    {#each data.units as row}
      <a
        class:active={row.unit.id === data.unitId}
        href={`/learning/courses/${data.courseId}/units/${row.unit.id}`}
      >
        <span>#{row.position}</span>
        <strong>{row.unit.title}</strong>
      </a>
    {/each}
  </nav>

  {#if data.message === "submitted"}
    <p class="flash flash-success">Abgabe gespeichert.</p>
  {/if}

  {#if form?.message}
    <p class="flash flash-error">{form.message}</p>
  {/if}

  {#if data.selectedUnit?.unit.unit_type === "modular"}
    <section class="panel">
      <h3>Graph</h3>
      {#if data.graph}
        {#each data.graph.phases as phase}
          <div class="phase">
            <h4>{phase.position}. {phase.title}</h4>
            <div class="module-grid">
              {#each data.graph.modules.filter((module) => module.phase_id === phase.id) as module}
                <a
                  class={`module-card status-${module.status}`}
                  href={moduleHref(module.id)}
                >
                  <strong>{module.title}</strong>
                  <span>{module.tasks_done}/{module.tasks_total} Aufgaben</span>
                  <span>{module.materials_count} Materialien</span>
                </a>
              {/each}
            </div>
          </div>
        {/each}
      {:else}
        <p class="empty">Der Graph konnte nicht geladen werden.</p>
      {/if}
    </section>

    <section class="panel">
      <h3>Aktives Modul</h3>
      {#if data.activeModule}
        <h4>{data.activeModule.module.title}</h4>
        <div class="stack">
          {#each data.activeModule.materials as material}
            <article class="card">
              <strong>{material.title}</strong>
              {#if material.kind === "markdown"}
                <pre>{material.body_md}</pre>
              {:else}
                <p class="empty">
                  Datei-Material · {material.filename_original || material.mime_type || "Download im Umbau"}
                </p>
              {/if}
            </article>
          {/each}

          {#each data.activeModule.tasks as task}
            <article class="task-card" id={`task-${task.id}`}>
              <header>
                <h4>Aufgabe</h4>
                <a href={historyHref(task.id)}>Verlauf</a>
              </header>

              <pre>{task.instruction_md}</pre>

              {#if task.kind === "h5p" && task.h5p?.content_id}
                <H5PTaskPlayer
                  courseId={data.courseId}
                  taskId={task.id}
                  contentId={task.h5p.content_id}
                />
              {:else}
                <form method="POST" enctype="multipart/form-data" class="submit-form">
                  <input type="hidden" name="task_id" value={task.id} />
                  <input type="hidden" name="task_kind" value={task.kind} />
                  <input type="hidden" name="unit_type" value="modular" />
                  <input type="hidden" name="module_id" value={data.activeModule.module.id} />

                  {#if !uploadOnly(task)}
                    <label>
                      Textantwort
                      <textarea name="text_body" rows="6"></textarea>
                    </label>
                  {/if}

                  <label>
                    {uploadOnly(task) ? "Datei hochladen" : "Optional Datei hochladen"}
                    <input name="upload_file" type="file" />
                  </label>

                  <button type="submit">Abgeben</button>
                </form>
              {/if}

              {#if isHistoryOpen(task.id)}
                <div class="history">
                  {#if data.history.length}
                    {#each data.history as submission}
                      <article class="history-entry">
                        <strong>Versuch {submission.attempt_nr}</strong>
                        <span>{humanStatus(submission)}</span>
                        {#if submission.text_body}
                          <pre>{submission.text_body}</pre>
                        {/if}
                        {#if submission.feedback_md}
                          <pre>{submission.feedback_md}</pre>
                        {/if}
                      </article>
                    {/each}
                  {:else}
                    <p class="empty">Noch keine Abgaben fuer diese Aufgabe.</p>
                  {/if}
                </div>
              {/if}
            </article>
          {/each}
        </div>
      {:else}
        <p class="empty">Waehle im Graphen ein offenes Modul aus.</p>
      {/if}
    </section>
  {:else}
    <div class="stack">
      {#each data.sections as section}
        <section class="panel">
          <h3>{section.section.position}. {section.section.title}</h3>

          {#if !section.materials.length && !section.tasks.length}
            <p class="empty">Noch keine Inhalte freigeschaltet.</p>
          {/if}

          {#each section.materials as material}
            <article class="card">
              <strong>{material.title}</strong>
              {#if material.kind === "markdown"}
                <pre>{material.body_md}</pre>
              {:else}
                <p class="empty">
                  Datei-Material · {material.filename_original || material.mime_type || "Download im Umbau"}
                </p>
              {/if}
            </article>
          {/each}

          {#each section.tasks as task}
            <article class="task-card" id={`task-${task.id}`}>
              <header>
                <h4>Aufgabe</h4>
                <a href={historyHref(task.id)}>Verlauf</a>
              </header>

              <pre>{task.instruction_md}</pre>

              {#if task.criteria.length}
                <ul>
                  {#each task.criteria as criterion}
                    <li>{criterion}</li>
                  {/each}
                </ul>
              {/if}

              {#if task.kind === "h5p" && task.h5p?.content_id}
                <H5PTaskPlayer
                  courseId={data.courseId}
                  taskId={task.id}
                  contentId={task.h5p.content_id}
                />
              {:else}
                <form method="POST" enctype="multipart/form-data" class="submit-form">
                  <input type="hidden" name="task_id" value={task.id} />
                  <input type="hidden" name="task_kind" value={task.kind} />
                  <input type="hidden" name="unit_type" value="linear" />

                  {#if !uploadOnly(task)}
                    <label>
                      Textantwort
                      <textarea name="text_body" rows="6"></textarea>
                    </label>
                  {/if}

                  <label>
                    {uploadOnly(task) ? "Datei hochladen" : "Optional Datei hochladen"}
                    <input name="upload_file" type="file" />
                  </label>

                  <button type="submit">Abgeben</button>
                </form>
              {/if}

              {#if isHistoryOpen(task.id)}
                <div class="history">
                  {#if data.history.length}
                    {#each data.history as submission}
                      <article class="history-entry">
                        <strong>Versuch {submission.attempt_nr}</strong>
                        <span>{humanStatus(submission)}</span>
                        {#if submission.text_body}
                          <pre>{submission.text_body}</pre>
                        {/if}
                        {#if submission.feedback_md}
                          <pre>{submission.feedback_md}</pre>
                        {/if}
                      </article>
                    {/each}
                  {:else}
                    <p class="empty">Noch keine Abgaben fuer diese Aufgabe.</p>
                  {/if}
                </div>
              {/if}
            </article>
          {/each}
        </section>
      {/each}
    </div>
  {/if}
</section>

<style>
  .workspace {
    display: grid;
    gap: 1rem;
  }

  .hero,
  .panel,
  .task-card,
  .card {
    background: rgba(255, 250, 243, 0.92);
    border: 1px solid #eadfd2;
    border-radius: 1.25rem;
  }

  .hero,
  .panel {
    padding: 1.25rem;
  }

  .hero {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: start;
  }

  .kicker,
  .lead,
  .empty,
  .back-link,
  .history-entry span,
  .module-card span {
    color: #6f6b86;
  }

  .kicker {
    margin: 0 0 0.35rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.85rem;
  }

  h2,
  h3,
  h4,
  pre {
    margin-top: 0;
  }

  .unit-switcher {
    display: flex;
    gap: 0.75rem;
    overflow-x: auto;
  }

  .unit-switcher a,
  .module-card {
    display: grid;
    gap: 0.2rem;
    padding: 0.85rem 1rem;
    border-radius: 1rem;
    border: 1px solid #eadfd2;
    background: #fffdf9;
    color: inherit;
    text-decoration: none;
  }

  .unit-switcher a.active {
    border-color: #286983;
    box-shadow: inset 0 0 0 1px #286983;
  }

  .stack,
  .history {
    display: grid;
    gap: 1rem;
  }

  .task-card,
  .card,
  .history-entry {
    padding: 1rem;
  }

  .task-card header {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: baseline;
  }

  .submit-form {
    display: grid;
    gap: 0.9rem;
  }

  .submit-form label {
    display: grid;
    gap: 0.35rem;
    color: #393552;
  }

  textarea,
  input[type="file"] {
    font: inherit;
  }

  textarea {
    min-height: 8rem;
    padding: 0.75rem;
    border-radius: 0.9rem;
    border: 1px solid #d7c7b7;
    background: #fffdf9;
  }

  button {
    width: fit-content;
    border: 0;
    border-radius: 999px;
    padding: 0.75rem 1.1rem;
    background: #286983;
    color: #fffaf3;
    font: inherit;
    cursor: pointer;
  }

  pre {
    white-space: pre-wrap;
    font: inherit;
    color: #393552;
  }

  .flash {
    margin: 0;
    padding: 0.85rem 1rem;
    border-radius: 1rem;
  }

  .flash-success {
    background: rgba(86, 148, 111, 0.14);
    color: #33673b;
  }

  .flash-error {
    background: rgba(180, 99, 122, 0.14);
    color: #8c4351;
  }

  .module-grid {
    display: grid;
    gap: 0.75rem;
    grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
  }

  .status-locked {
    opacity: 0.55;
  }

  .status-done {
    border-color: #56946f;
  }

  @media (max-width: 900px) {
    .hero {
      flex-direction: column;
    }
  }
</style>
