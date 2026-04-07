<script lang="ts">
  import { enhance } from "$app/forms";
  import H5PTaskPlayer from "$lib/components/H5PTaskPlayer.svelte";
  import MarkdownWysiwygEditor from "$lib/components/learning-unit/MarkdownWysiwygEditor.svelte";
  import { renderMarkdown } from "$lib/utils/markdown";
  import type { LearningSubmission, LearningTask } from "$lib/types/learning";
  import type { SubmitFunction } from "@sveltejs/kit";

  let {
    courseId,
    task,
    taskTitle = "Aufgabe",
    contextLabel = null,
    unitType,
    moduleId = null,
    history = [],
    domId = undefined,
    expanded = true,
    submitted = false,
    message = null,
    errorMessage = null,
    feedbackPending = false,
    feedbackStatusMessage = null,
    pendingIntent = null,
    submissionFocused = false,
    initialSubmissionMode = null,
    reviewPanelOpen = false,
    enhanceSubmit = undefined,
    onToggle = null,
    onToggleReviewPanel = null,
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
    history?: LearningSubmission[];
    domId?: string;
    expanded?: boolean;
    submitted?: boolean;
    message?: string | null;
    errorMessage?: string | null;
    feedbackPending?: boolean;
    feedbackStatusMessage?: string | null;
    pendingIntent?: "feedback" | "submit" | null;
    submissionFocused?: boolean;
    initialSubmissionMode?: "text" | "upload" | null;
    reviewPanelOpen?: boolean;
    enhanceSubmit?: SubmitFunction;
    onToggle?: (() => void) | null;
    onToggleReviewPanel?: (() => void) | null;
    onEnterSubmissionWorkspace?: (() => void) | null;
    onEnterUploadWorkspace?: (() => void) | null;
    onExitSubmissionWorkspace?: (() => void) | null;
  } = $props();

  type SummaryTab = "submission" | "feedback" | "evaluation";
  let activeSummaryTab = $state<SummaryTab>("submission");
  let draftText = $state("");

  function uploadOnly(): boolean {
    return task.kind === "visual" || task.kind === "scratch" || task.kind === "calliope";
  }

  function hasSubmission(): boolean {
    return Boolean(task.has_submission || submitted || history.length > 0);
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

  function actionLabel(): string {
    return hasRetryState() ? "Erneut bearbeiten" : "Aufgabe bearbeiten";
  }

  function showSubmissionSummary(): boolean {
    return task.kind !== "h5p" && reviewPanelOpen && hasSubmission();
  }

  function showInlinePendingNote(): boolean {
    return Boolean(submissionFocused && feedbackPendingMessage() && !showSubmissionSummary());
  }

  function showStandalonePendingNote(): boolean {
    return Boolean(!submissionFocused && feedbackPendingMessage() && !showSubmissionSummary());
  }

  function hasRetryState(): boolean {
    return hasSubmission() || Boolean(feedbackPending && pendingIntent === "submit");
  }

  function fileSummary(submission: LearningSubmission): string {
    const first = submission.files?.[0];
    if (!first) {
      return "Keine Datei hinterlegt.";
    }
    return `${first.mime} · ${Math.max(1, Math.round(first.size / 1024))} KB`;
  }

  function evaluationSummary(submission: LearningSubmission): string {
    const score = submission.analysis_json?.score;
    if (typeof score === "number") {
      return `Punktestand: ${score}`;
    }
    if (submission.score_raw !== null && submission.score_raw !== undefined) {
      return `${submission.score_raw}/${submission.score_max ?? 0}`;
    }
    return submission.analysis_status;
  }

  function summaryPanelLabel(tab: SummaryTab): string {
    if (tab === "submission") {
      return "Abgabe";
    }
    if (tab === "feedback") {
      return "Rückmeldung";
    }
    return "Auswertung";
  }

  function feedbackPendingMessage(): string | null {
    if (feedbackPending) {
      if (feedbackStatusMessage) {
        return feedbackStatusMessage;
      }
      return pendingIntent === "submit" ? "Abgabe wird verarbeitet ..." : "Rückmeldung wird erstellt ...";
    }
    return feedbackStatusMessage;
  }

  function renderEvaluationCriteria(submission: LearningSubmission): boolean {
    return Boolean(submission.analysis_json?.criteria_results?.length);
  }

  function updateDraft(value: string) {
    draftText = value;
  }

  $effect(() => {
    if (!reviewPanelOpen) {
      activeSummaryTab = "submission";
    }
  });

</script>

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
        <div class="markdown-prose">
          {@html renderMarkdown(task.instruction_md)}
        </div>

        {#if showSubmissionSummary()}
          <section class="learning-task-submission-summary" aria-label="Meine Abgabe">
            <header class="learning-task-submission-summary__header">
              <div class="learning-task-submission-summary__copy">
                <p class="workspace-label">Meine Abgabe</p>
                {#if latestSubmission()}
                  <p class="learning-task-submission-summary__meta">{latestSubmissionOrThrow().created_at}</p>
                {/if}
              </div>
            </header>

            {#if feedbackPendingMessage()}
              <p class="workspace-note">{feedbackPendingMessage()}</p>
            {/if}

            <div class="learning-task-submission-summary__tabs" role="tablist" aria-label="Letzte Abgabe">
              <button
                class:workspace-tab--active={activeSummaryTab === "submission"}
                class="workspace-tab"
                role="tab"
                type="button"
                aria-selected={activeSummaryTab === "submission"}
                onclick={() => (activeSummaryTab = "submission")}
              >
                Abgabe
              </button>
              <button
                class:workspace-tab--active={activeSummaryTab === "feedback"}
                class="workspace-tab"
                role="tab"
                type="button"
                aria-selected={activeSummaryTab === "feedback"}
                onclick={() => (activeSummaryTab = "feedback")}
              >
                Rückmeldung
              </button>
              <button
                class:workspace-tab--active={activeSummaryTab === "evaluation"}
                class="workspace-tab"
                role="tab"
                type="button"
                aria-selected={activeSummaryTab === "evaluation"}
                onclick={() => (activeSummaryTab = "evaluation")}
              >
                Auswertung
              </button>
            </div>

            <div class="learning-task-submission-summary__panel" role="tabpanel" aria-label={summaryPanelLabel(activeSummaryTab)}>
              {#if activeSummaryTab === "submission"}
                {#if latestSubmission() && latestSubmissionOrThrow().text_body}
                  <div class="markdown-prose">
                    <p>{latestSubmissionOrThrow().text_body}</p>
                  </div>
                {:else if latestSubmission()}
                  <p class="learning-task-submission-summary__plain">{fileSummary(latestSubmissionOrThrow())}</p>
                {:else if feedbackPending}
                  <p class="learning-task-submission-summary__plain">Die aktuelle Abgabe wird vorbereitet.</p>
                {:else}
                  <p class="learning-task-submission-summary__plain">Es liegt noch keine Abgabe vor.</p>
                {/if}
              {:else if activeSummaryTab === "feedback"}
                {#if feedbackPendingMessage()}
                  <p class="workspace-note">{feedbackPendingMessage()}</p>
                {:else if latestSubmission() && latestSubmissionOrThrow().feedback_md}
                  <div class="markdown-prose">
                    {@html renderMarkdown(latestSubmissionOrThrow().feedback_md)}
                  </div>
                {:else}
                  <p class="learning-task-submission-summary__plain">Es liegt noch keine Rückmeldung vor.</p>
                {/if}
              {:else}
                {#if latestSubmission() && renderEvaluationCriteria(latestSubmissionOrThrow())}
                  <ul class="learning-unit-criteria">
                    {#each latestSubmissionOrThrow().analysis_json?.criteria_results ?? [] as criterion}
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
                {:else if latestSubmission()}
                  <p class="learning-task-submission-summary__plain">{evaluationSummary(latestSubmissionOrThrow())}</p>
                {:else if feedbackPendingMessage()}
                  <p class="workspace-note">{feedbackPendingMessage()}</p>
                {:else}
                  <p class="learning-task-submission-summary__plain">Es liegt noch keine Auswertung vor.</p>
                {/if}
              {/if}
            </div>
          </section>
        {/if}

        {#if submissionFocused}
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

            {#if showInlinePendingNote()}
              <p class="workspace-note">{feedbackPendingMessage()}</p>
            {/if}

            {#if task.kind === "h5p"}
              {#if task.h5p?.content_id}
                <H5PTaskPlayer {courseId} taskId={task.id} contentId={task.h5p.content_id} />
              {:else}
                <p class="workspace-note">Diese H5P-Aufgabe ist noch nicht bereit.</p>
              {/if}
            {:else if initialSubmissionMode === "upload" || uploadOnly()}
              <form class="learning-submission-upload" method="POST" enctype="multipart/form-data" use:enhance={enhanceSubmit}>
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
                  <button class="workspace-top-action workspace-top-action--quiet" name="submission_intent" type="submit" value="feedback" disabled={feedbackPending}>
                    Rückmeldung einholen
                  </button>
                  <button class="workspace-top-action workspace-top-action--accent" name="submission_intent" type="submit" value="submit" disabled={feedbackPending}>
                    Endgültig abgeben
                  </button>
                </div>
              </form>
            {:else}
              <form class="learning-submission-editor learning-submission-editor--immersive" method="POST" enctype="multipart/form-data" use:enhance={enhanceSubmit}>
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
                    value={draftText}
                    placeholder="Schreibe hier deine Lösung."
                    onInput={updateDraft}
                  />
                </section>
                <div class="learning-submission-editor__actions">
                  <button class="workspace-top-action workspace-top-action--quiet" name="submission_intent" type="submit" value="feedback" disabled={feedbackPending}>
                    Rückmeldung einholen
                  </button>
                  <button class="workspace-top-action workspace-top-action--accent" name="submission_intent" type="submit" value="submit" disabled={feedbackPending}>
                    Endgültig abgeben
                  </button>
                </div>
              </form>
            {/if}

            {#if errorMessage}
              <p class="flash flash-error">{errorMessage}</p>
            {/if}
          </section>
        {:else}
          {#if showStandalonePendingNote()}
            <p class="workspace-note">{feedbackPendingMessage()}</p>
          {/if}
          <div class="learning-task-cta-row">
            {#if hasSubmission() && task.kind !== "h5p"}
              <button
                class:workspace-top-action--active={reviewPanelOpen}
                class="workspace-top-action workspace-top-action--quiet"
                type="button"
                onclick={() => onToggleReviewPanel?.()}
              >
                Meine Abgabe
              </button>
            {/if}
            <button
              class:workspace-top-action--accent={!hasRetryState()}
              class:workspace-top-action--quiet={hasRetryState()}
              class="workspace-top-action"
              type="button"
              onclick={() => onEnterSubmissionWorkspace?.()}
            >
              {actionLabel()}
            </button>
          </div>
        {/if}
      </div>
    {/if}
</article>
