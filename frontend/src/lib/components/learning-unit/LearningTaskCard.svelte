<script lang="ts">
  import H5PTaskPlayer from "$lib/components/H5PTaskPlayer.svelte";
  import LearningResponseGroup from "$lib/components/learning-unit/LearningResponseGroup.svelte";
  import MarkdownWysiwygEditor from "$lib/components/learning-unit/MarkdownWysiwygEditor.svelte";
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

  function latestSubmission(): LearningSubmission | null {
    return history[0] ?? null;
  }

  function latestSubmissionOrThrow(): LearningSubmission {
    const submission = latestSubmission();
    if (!submission) {
      throw new Error("submission_missing");
    }
    return submission;
  }

  function taskKicker(): string {
    return contextLabel ?? "Aufgabe";
  }

  function taskStateLabel(): string {
    if (submitted || history.length > 0) {
      return "Antwortstatus";
    }
    return "Nächster Schritt";
  }

</script>

{#if submissionFocused}
  <article class="learning-work-item learning-work-item--task" id={domId}>
    <button class="learning-work-item__toggle" type="button" title={taskTitle} onclick={() => onToggle?.()}>
      <div class="learning-work-item__header">
        <div class="learning-work-item__header-copy">
          <span class="learning-work-item__kicker">{taskKicker()}</span>
          <span class="learning-work-item__title">{taskTitle}</span>
        </div>
        <span class="learning-work-item__toggle-icon learning-work-item__toggle-icon--expanded" aria-hidden="true">
          <svg viewBox="0 0 20 20">
            <path d="M6.25 8.25 10 12l3.75-3.75" />
          </svg>
        </span>
      </div>
    </button>

    <div class="learning-work-item__body">
      <div class="markdown-prose">
        {@html renderMarkdown(task.instruction_md)}
      </div>

      <section class="learning-task-inline-editor">
        <header class="learning-task-inline-editor__header">
          <div>
            <p class="workspace-label">{taskKicker()}</p>
            <h5 class="learning-task-inline-editor__title">{taskTitle}</h5>
            <p class="learning-task-inline-editor__copy">Die Bearbeitung bleibt Teil derselben Arbeitsfläche.</p>
          </div>
          <button class="workspace-top-action workspace-top-action--quiet" type="button" onclick={() => onExitSubmissionWorkspace?.()}>
            Bearbeitung schließen
          </button>
        </header>

        {#if task.kind === "h5p"}
          {#if task.h5p?.content_id}
            <H5PTaskPlayer {courseId} taskId={task.id} contentId={task.h5p.content_id} />
          {:else}
            <p class="workspace-note">Diese H5P-Aufgabe ist noch nicht bereit.</p>
          {/if}
        {:else if initialSubmissionMode === "upload" || uploadOnly()}
          <form class="learning-submission-upload" method="POST" enctype="multipart/form-data">
            <input type="hidden" name="task_id" value={task.id} />
            <input type="hidden" name="task_kind" value={task.kind} />
            <input type="hidden" name="unit_type" value={unitType} />
            {#if moduleId}
              <input type="hidden" name="module_id" value={moduleId} />
            {/if}
            <label class="learning-submission-upload__dropzone">
              <span class="learning-submission-upload__title">Datei auswählen</span>
              <span class="learning-submission-upload__copy">Bild oder PDF hochladen</span>
              <input name="upload_file" type="file" />
            </label>
            <div class="learning-submission-editor__actions">
              <button class="workspace-top-action workspace-top-action--quiet" name="submission_intent" type="submit" value="feedback">
                Rückmeldung einholen
              </button>
              <button class="workspace-top-action workspace-top-action--accent" name="submission_intent" type="submit" value="submit">
                Endgültig abgeben
              </button>
            </div>
          </form>
        {:else}
          <form class="learning-submission-editor learning-submission-editor--immersive" method="POST" enctype="multipart/form-data">
            <input type="hidden" name="task_id" value={task.id} />
            <input type="hidden" name="task_kind" value={task.kind} />
            <input type="hidden" name="unit_type" value={unitType} />
            {#if moduleId}
              <input type="hidden" name="module_id" value={moduleId} />
            {/if}
            <section class="learning-submission-editor__field">
              <span>Deine Lösung</span>
              <MarkdownWysiwygEditor
                name="text_body"
                value=""
                placeholder="Schreibe hier deine Lösung."
                onInput={() => {}}
              />
            </section>
            <div class="learning-submission-editor__actions">
              <button class="workspace-top-action workspace-top-action--quiet" name="submission_intent" type="submit" value="feedback">
                Rückmeldung einholen
              </button>
              <button class="workspace-top-action workspace-top-action--accent" name="submission_intent" type="submit" value="submit">
                Endgültig abgeben
              </button>
            </div>
          </form>
        {/if}

        {#if errorMessage}
          <p class="flash flash-error">{errorMessage}</p>
        {/if}

        {#if hasSubmissionHistory() && latestSubmission()}
          <LearningResponseGroup submission={latestSubmissionOrThrow()} />
        {/if}
      </section>
    </div>
  </article>
{:else}
  <article class:learning-work-item--collapsed={!expanded} class="learning-work-item learning-work-item--task" id={domId}>
    <button
      class:learning-work-item__toggle--collapsed={!expanded}
      class="learning-work-item__toggle"
      type="button"
      title={taskTitle}
    onclick={() => onToggle?.()}
  >
    <div class="learning-work-item__header">
      <div class="learning-work-item__header-copy">
        <span class="learning-work-item__kicker">{taskKicker()}</span>
        <span class="learning-work-item__title">{taskTitle}</span>
      </div>

      <span class:learning-work-item__toggle-icon--expanded={expanded} class="learning-work-item__toggle-icon" aria-hidden="true">
        <svg viewBox="0 0 20 20">
            <path d="M6.25 8.25 10 12l3.75-3.75" />
          </svg>
        </span>
      </div>
    </button>

    {#if expanded}
      <div class="learning-work-item__body">
      {#if task.kind === "h5p"}
        {#if task.h5p?.content_id}
          <H5PTaskPlayer
            {courseId}
            taskId={task.id}
            contentId={task.h5p.content_id}
          />
        {:else}
          <p class="workspace-note">Diese H5P-Aufgabe ist noch nicht bereit.</p>
        {/if}
      {:else}
        <div class="markdown-prose">
          {@html renderMarkdown(task.instruction_md)}
        </div>

        <section class="learning-work-item__start-card">
          <div class="learning-work-item__start-card-actions">
            <div class="learning-work-item__start-card-copy">
              <p class="workspace-label">{taskStateLabel()}</p>
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

        {#if hasSubmissionHistory() && latestSubmission()}
          <LearningResponseGroup submission={latestSubmissionOrThrow()} />
        {/if}
      {/if}
      </div>
    {/if}
  </article>
{/if}
