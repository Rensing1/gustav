<script lang="ts">
  import H5PTaskPlayer from "$lib/components/H5PTaskPlayer.svelte";
  import type { LearningSubmission, LearningTask } from "$lib/types/learning";

  let {
    courseId,
    task,
    unitType,
    moduleId = null,
    historyHref,
    historyOpen = false,
    history = []
  }: {
    courseId: string;
    task: LearningTask;
    unitType: "linear" | "modular";
    moduleId?: string | null;
    historyHref: string;
    historyOpen?: boolean;
    history?: LearningSubmission[];
  } = $props();

  function uploadOnly(): boolean {
    return task.kind === "visual" || task.kind === "scratch" || task.kind === "calliope";
  }

  function humanStatus(submission: LearningSubmission): string {
    if (submission.kind === "h5p" && submission.score_raw !== null && submission.score_raw !== undefined) {
      return `${submission.analysis_status} · ${submission.score_raw}/${submission.score_max ?? 0}`;
    }
    return submission.analysis_status;
  }
</script>

<article class="task-card learning-unit-task-card" id={`task-${task.id}`}>
  <header class="learning-unit-task-card__header">
    <div class="learning-unit-task-card__copy">
      <p class="workspace-label">Aufgabe</p>
      <h4>Aufgabe</h4>
    </div>
    <a class="learning-unit-task-card__history-link" href={historyHref}>Verlauf</a>
  </header>

  <pre>{task.instruction_md}</pre>

  {#if task.criteria.length}
    <ul class="learning-unit-criteria">
      {#each task.criteria as criterion}
        <li>{criterion}</li>
      {/each}
    </ul>
  {/if}

  {#if task.kind === "h5p" && task.h5p?.content_id}
    <H5PTaskPlayer
      {courseId}
      taskId={task.id}
      contentId={task.h5p.content_id}
    />
  {:else}
    <form method="POST" enctype="multipart/form-data" class="submit-form">
      <input type="hidden" name="task_id" value={task.id} />
      <input type="hidden" name="task_kind" value={task.kind} />
      <input type="hidden" name="unit_type" value={unitType} />
      {#if moduleId}
        <input type="hidden" name="module_id" value={moduleId} />
      {/if}

      {#if !uploadOnly()}
        <label>
          Textantwort
          <textarea name="text_body" rows="6"></textarea>
        </label>
      {/if}

      <label>
        {uploadOnly() ? "Datei hochladen" : "Optional Datei hochladen"}
        <input name="upload_file" type="file" />
      </label>

      <button type="submit">Abgeben</button>
    </form>
  {/if}

  {#if historyOpen}
    <div class="history">
      {#if history.length}
        {#each history as submission}
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
        <p class="learning-unit-empty-copy">Noch keine Abgaben für diese Aufgabe.</p>
      {/if}
    </div>
  {/if}
</article>
