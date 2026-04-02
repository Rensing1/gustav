<script lang="ts">
  import H5PTaskPlayer from "$lib/components/H5PTaskPlayer.svelte";
  import type { LearningSubmission, LearningTask } from "$lib/types/learning";

  let {
    courseId,
    task,
    taskTitle = "Aufgabe",
    contextLabel = null,
    unitType,
    moduleId = null,
    historyHref,
    historyOpen = false,
    history = [],
    domId = undefined,
    expanded = true,
    onToggle = null
  }: {
    courseId: string;
    task: LearningTask;
    taskTitle?: string;
    contextLabel?: string | null;
    unitType: "linear" | "modular";
    moduleId?: string | null;
    historyHref: string;
    historyOpen?: boolean;
    history?: LearningSubmission[];
    domId?: string;
    expanded?: boolean;
    onToggle?: (() => void) | null;
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

<article class:learning-work-item--collapsed={!expanded} class="learning-work-item learning-work-item--task" id={domId}>
  <button class="learning-work-item__toggle" type="button" onclick={() => onToggle?.()}>
    <div class="learning-work-item__header">
      <div class="learning-work-item__copy">
        <div class="learning-work-item__kicker-row">
          {#if contextLabel}
            <span class="learning-work-item__context">{contextLabel}</span>
          {/if}
          <span class="learning-work-item__kicker">Aufgabe</span>
        </div>
        <h4>{taskTitle}</h4>
      </div>

      <span class:learning-work-item__toggle-icon--expanded={expanded} class="learning-work-item__toggle-icon" aria-hidden="true">
        ▾
      </span>
    </div>
  </button>

  {#if expanded}
    <div class="learning-work-item__body">
      <div class="learning-work-item__actions">
        <a class="learning-work-item__link" href={historyHref}>Verlauf</a>
      </div>

      <pre>{task.instruction_md}</pre>

      {#if task.criteria.length}
        <ul class="learning-unit-criteria">
          {#each task.criteria as criterion}
            <li>{criterion}</li>
          {/each}
        </ul>
      {/if}

      {#if task.kind === "h5p" && task.h5p?.content_id}
        <section class="learning-work-item__support learning-work-item__support--open">
          <header class="learning-work-item__support-header">
            <h5>Interaktive Aufgabe</h5>
          </header>
          <H5PTaskPlayer
            {courseId}
            taskId={task.id}
            contentId={task.h5p.content_id}
          />
        </section>
      {:else}
        <details class="learning-work-item__support">
          <summary>Abgabe</summary>
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
        </details>
      {/if}

      {#if historyOpen}
        <details class="learning-work-item__support learning-work-item__support--open">
          <summary>Verlauf</summary>
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
        </details>
      {/if}
    </div>
  {/if}
</article>
