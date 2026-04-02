<script lang="ts">
  import H5PTaskPlayer from "$lib/components/H5PTaskPlayer.svelte";
  import LearningSubmissionWorkspace from "$lib/components/learning-unit/LearningSubmissionWorkspace.svelte";
  import { renderMarkdown } from "$lib/utils/markdown";
  import type { LearningSubmission, LearningTask } from "$lib/types/learning";

  let {
    courseId,
    task,
    taskTitle = "Aufgabe",
    contextLabel = null,
    unitType,
    moduleId = null,
    historyOpen = false,
    history = [],
    domId = undefined,
    expanded = true,
    submitted = false,
    errorMessage = null,
    submissionFocused = false,
    onToggle = null,
    onEnterSubmissionWorkspace = null,
    onExitSubmissionWorkspace = null
  }: {
    courseId: string;
    task: LearningTask;
    taskTitle?: string;
    contextLabel?: string | null;
    unitType: "linear" | "modular";
    moduleId?: string | null;
    historyOpen?: boolean;
    history?: LearningSubmission[];
    domId?: string;
    expanded?: boolean;
    submitted?: boolean;
    errorMessage?: string | null;
    submissionFocused?: boolean;
    onToggle?: (() => void) | null;
    onEnterSubmissionWorkspace?: (() => void) | null;
    onExitSubmissionWorkspace?: (() => void) | null;
  } = $props();

  function uploadOnly(): boolean {
    return task.kind === "visual" || task.kind === "scratch" || task.kind === "calliope";
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
      <div class="markdown-prose">
        {@html renderMarkdown(task.instruction_md)}
      </div>

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
        {#if submissionFocused}
          <LearningSubmissionWorkspace
            {courseId}
            {task}
            {taskTitle}
            {unitType}
            {moduleId}
            initialHistory={history}
            initialHistoryLoaded={historyOpen}
            initialTab={submitted ? "history" : "submit"}
            {submitted}
            {errorMessage}
            onClose={onExitSubmissionWorkspace}
          />
        {:else}
          <section class="learning-work-item__support learning-work-item__support--open">
            <header class="learning-work-item__support-header">
              <h5>Abgabe</h5>
            </header>
            <p class="learning-unit-empty-copy">
              Öffne den Abgabe-Arbeitsbereich, um deine Lösung zu schreiben, hochzuladen oder frühere Rückmeldungen zu lesen.
            </p>
            <button class="workspace-link-action" type="button" onclick={() => onEnterSubmissionWorkspace?.()}>
              Lösung schreiben
            </button>
          </section>
        {/if}
      {/if}
    </div>
  {/if}
</article>
