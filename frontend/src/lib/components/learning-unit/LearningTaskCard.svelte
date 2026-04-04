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
    message = null,
    errorMessage = null,
    submissionFocused = false,
    initialSubmissionMode = null,
    onToggle = null,
    onEnterSubmissionWorkspace = null,
    onEnterUploadWorkspace = null,
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
    message?: string | null;
    errorMessage?: string | null;
    submissionFocused?: boolean;
    initialSubmissionMode?: "text" | "upload" | null;
    onToggle?: (() => void) | null;
    onEnterSubmissionWorkspace?: (() => void) | null;
    onEnterUploadWorkspace?: (() => void) | null;
    onExitSubmissionWorkspace?: (() => void) | null;
  } = $props();

  function uploadOnly(): boolean {
    return task.kind === "visual" || task.kind === "scratch" || task.kind === "calliope";
  }

  function hasSubmissionHistory(): boolean {
    return submitted || historyOpen || history.length > 0;
  }

</script>

{#if submissionFocused}
  <article class="learning-task-workspace" id={domId}>
    <header class="learning-task-workspace__header">
      <div class="learning-task-workspace__copy">
        <div class="learning-task-workspace__eyebrow">
          {#if contextLabel}
            <span class="learning-task-workspace__context">{contextLabel}</span>
          {/if}
          <span class="learning-task-workspace__kicker">Aufgabe</span>
        </div>
        <h4>{taskTitle}</h4>
        <div class="learning-task-workspace__statement markdown-prose">
          {@html renderMarkdown(task.instruction_md)}
        </div>
      </div>
    </header>

    <LearningSubmissionWorkspace
      {courseId}
      {task}
      {taskTitle}
      {unitType}
      {moduleId}
      initialHistory={history}
      initialHistoryLoaded={historyOpen}
      initialTab={submitted ? "history" : "submit"}
      initialMode={initialSubmissionMode ?? (uploadOnly() ? "upload" : "text")}
      {submitted}
      {message}
      {errorMessage}
      onClose={onExitSubmissionWorkspace}
    />
  </article>
{:else}
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
        <section class="learning-work-item__start-card">
          <div class="learning-work-item__start-card-actions">
            <div class="learning-work-item__start-card-copy">
              <p class="workspace-label">Nächster Schritt</p>
              <h5>Aufgabe bearbeiten</h5>
              {#if hasSubmissionHistory()}
                <p class="learning-work-item__start-card-hint">Frühere Rückmeldungen und Abgaben sind vorhanden.</p>
              {/if}
            </div>
            <button class="workspace-top-action workspace-top-action--accent" type="button" onclick={() => onEnterSubmissionWorkspace?.()}>
              Aufgabe bearbeiten
            </button>
          </div>
        </section>
      {/if}
      </div>
    {/if}
  </article>
{/if}
