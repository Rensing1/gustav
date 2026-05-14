<script lang="ts">
  import { enhance } from "$app/forms";
  import H5PTaskPlayer from "$lib/components/H5PTaskPlayer.svelte";
  import LearningSubmissionArtifactView from "$lib/components/learning-unit/LearningSubmissionArtifactView.svelte";
  import MarkdownWysiwygEditor from "$lib/components/learning-unit/MarkdownWysiwygEditor.svelte";
  import { buildSubmissionArtifactView } from "$lib/utils/submission-artifacts";
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
    historyState = "loaded",
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
    compactLayout = false,
    enhanceSubmit = undefined,
    onToggle = null,
    onToggleReviewPanel = null,
    onEnterSubmissionWorkspace = null,
    onEnterUploadWorkspace = null,
    onExitSubmissionWorkspace = null,
    onSubmitUploadFeedback = null,
    onProgressPersisted = null
  }: {
    courseId: string;
    task: LearningTask;
    taskTitle?: string;
    contextLabel?: string | null;
    unitType: "linear" | "modular";
    moduleId?: string | null;
    history?: LearningSubmission[];
    historyState?: SubmissionHistoryLoadState;
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
    compactLayout?: boolean;
    enhanceSubmit?: SubmitFunction;
    onToggle?: (() => void) | null;
    onToggleReviewPanel?: (() => void) | null;
    onEnterSubmissionWorkspace?: (() => void) | null;
    onEnterUploadWorkspace?: (() => void) | null;
    onExitSubmissionWorkspace?: (() => void) | null;
    onSubmitUploadFeedback?: ((payload: {
      taskId: string;
      taskKind: UploadTaskKind;
      file: File;
      moduleId: string | null;
    }) => void | Promise<void>) | null;
    onProgressPersisted?: (() => void | Promise<void>) | null;
  } = $props();

  type SummaryTab = "submission" | "feedback" | "evaluation";
  type SubmissionMode = "text" | "upload";
  type SubmissionHistoryLoadState = "not_loaded" | "loading" | "loaded" | "failed" | "unavailable";
  type UploadTaskKind = Extract<LearningTask["kind"], "native" | "visual" | "scratch" | "calliope" | "filius">;
  type CompactTaskTone = "new" | "draft" | "pending" | "final" | "error";
  let activeSummaryTab = $state<SummaryTab>("submission");
  let draftText = $state("");
  let editorMode = $state<SubmissionMode>("text");
  let selectedUploadFile = $state<File | null>(null);
  let hideExistingUpload = $state(false);
  let uploadInput = $state<HTMLInputElement | null>(null);
  let lastSubmissionFocused = $state(false);

  function uploadOnly(): boolean {
    return task.kind === "visual" || task.kind === "scratch" || task.kind === "calliope" || task.kind === "filius";
  }

  function hasSubmission(): boolean {
    return Boolean(task.has_submission || submitted || history.length > 0);
  }

  function latestSubmissionIntent(): "feedback" | "submit" | null {
    return latestSubmission()?.intent ?? task.latest_submission_intent ?? null;
  }

  function latestSubmissionStatus(): "pending" | "extracted" | "completed" | "failed" | null {
    return latestSubmission()?.analysis_status ?? task.latest_submission_analysis_status ?? null;
  }

  function latestFinalSubmissionAt(): string | null {
    const fromHistory = history.find((entry) => entry.intent === "submit")?.created_at ?? null;
    return fromHistory ?? task.latest_final_submission_at ?? null;
  }

  function hasFinalSubmission(): boolean {
    return Boolean(latestFinalSubmissionAt());
  }

  function canFinalizeLatestDraft(): boolean {
    return latestSubmissionIntent() === "feedback" && latestSubmissionStatus() === "completed";
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
    if (!hasSubmission()) {
      return `${taskTitle} beginnen`;
    }
    return hasFinalSubmission() ? "Erneut bearbeiten" : "Entwurf weiterbearbeiten";
  }

  function taskPreviewLine(): string {
    const firstNonEmptyLine = task.instruction_md
      .split(/\r?\n/)
      .map((line) => line.trim())
      .find((line) => line.length > 0);

    return firstNonEmptyLine ?? taskTitle;
  }

  function showSubmissionSummary(): boolean {
    return task.kind !== "h5p" && reviewPanelOpen && hasSubmission();
  }

  function usesCompactTaskLayout(): boolean {
    return compactLayout;
  }

  function showInlinePendingNote(): boolean {
    return Boolean(submissionFocused && feedbackPendingMessage() && !showSubmissionSummary());
  }

  function showStandalonePendingNote(): boolean {
    return Boolean(!submissionFocused && feedbackPendingMessage() && !showSubmissionSummary());
  }

  function fileSummary(submission: LearningSubmission): string {
    const first = submission.files?.[0];
    if (!first) {
      return "Keine Datei hinterlegt.";
    }
    return `${first.mime} · ${Math.max(1, Math.round(first.size / 1024))} KB`;
  }

  function formatBytes(size: number | null | undefined): string {
    if (!size || size <= 0) {
      return "Datei";
    }
    if (size < 1024 * 1024) {
      return `${Math.max(1, Math.round(size / 1024))} KB`;
    }
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  }

  function isUploadSubmission(submission: LearningSubmission | null): boolean {
    return submission?.kind === "image" || submission?.kind === "file";
  }

  function currentUploadSubmission(): LearningSubmission | null {
    if (hideExistingUpload || selectedUploadFile) {
      return null;
    }
    const latest = latestSubmission();
    return isUploadSubmission(latest) ? latest : null;
  }

  function preferredEditorMode(): SubmissionMode {
    if (uploadOnly()) {
      return "upload";
    }
    if (initialSubmissionMode === "text" || initialSubmissionMode === "upload") {
      return initialSubmissionMode;
    }
    return isUploadSubmission(latestSubmission()) ? "upload" : "text";
  }

  function setEditorMode(next: SubmissionMode) {
    editorMode = next;
  }

  function editorModeIs(next: SubmissionMode): boolean {
    return editorMode === next;
  }

  function uploadTitle(): string {
    if (task.kind === "scratch") {
      return ".sb3-Datei auswählen";
    }
    if (task.kind === "calliope") {
      return ".hex-Datei auswählen";
    }
    if (task.kind === "filius") {
      return ".fls-Datei auswählen";
    }
    return "Datei auswählen";
  }

  function uploadCopy(): string {
    if (task.kind === "scratch") {
      return "Scratch-Datei (.sb3) hochladen";
    }
    if (task.kind === "calliope") {
      return "Calliope-Datei (.hex) hochladen";
    }
    if (task.kind === "filius") {
      return "Filius-Datei (.fls) hochladen";
    }
    if (task.kind === "visual") {
      return "Bild oder PDF auswählen";
    }
    return "Datei auswählen und als Entwurf hochladen";
  }

  function uploadAccept(): string | undefined {
    if (task.kind === "scratch") {
      return ".sb3,application/x.scratch.sb3";
    }
    if (task.kind === "calliope") {
      return ".hex,application/x.makecode.hex";
    }
    if (task.kind === "filius") {
      return ".fls,application/x.filius.fls";
    }
    return ".pdf,image/png,image/jpeg,application/pdf,image/png,image/jpeg";
  }

  function handleUploadSelection(event: Event) {
    const target = event.currentTarget;
    if (!(target instanceof HTMLInputElement)) {
      return;
    }
    selectedUploadFile = target.files?.[0] ?? null;
    hideExistingUpload = false;
  }

  function clearUploadSelection() {
    selectedUploadFile = null;
    hideExistingUpload = true;
    if (uploadInput) {
      uploadInput.value = "";
    }
  }

  function triggerUploadPicker() {
    uploadInput?.click();
  }

  function hasUploadReadyForSubmit(): boolean {
    return Boolean(selectedUploadFile);
  }

  function submitUploadFeedback() {
    if (!selectedUploadFile) {
      return;
    }
    void onSubmitUploadFeedback?.({
      taskId: task.id,
      taskKind: task.kind as UploadTaskKind,
      file: selectedUploadFile,
      moduleId
    });
  }

  function selectedUploadLabel(file: File): string {
    const type = file.type === "application/pdf" ? "PDF" : file.type.startsWith("image/") ? "Bild" : file.type || "Datei";
    return `${type} · ${formatBytes(file.size)}`;
  }

  function submittedFile(): { mime: string; size: number; url: string } | null {
    return latestSubmission()?.files?.[0] ?? null;
  }

  function submittedArtifact() {
    const submission = latestSubmission();
    return submission ? buildSubmissionArtifactView(submission) : null;
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

  function historyStateMessage(): string | null {
    if (latestSubmission()) {
      return null;
    }
    if (historyState === "loading") {
      return "Die Abgabe wird geladen ...";
    }
    if (historyState === "failed") {
      return "Die Abgabe konnte nicht geladen werden. Bitte versuche es erneut.";
    }
    if ((historyState === "not_loaded" || historyState === "unavailable") && hasSubmission()) {
      return "Die gespeicherte Abgabe ist momentan nicht verfügbar.";
    }
    return null;
  }

  function renderEvaluationCriteria(submission: LearningSubmission): boolean {
    return Boolean(submission.analysis_json?.criteria_results?.length);
  }

  function statusHeadline(): string {
    if (hasFinalSubmission()) {
      return `Final abgegeben am ${latestFinalSubmissionAt()}`;
    }
    if (latestSubmissionIntent() === "feedback" && latestSubmissionStatus() === "completed") {
      return "Entwurf mit Rückmeldung vorhanden";
    }
    if (latestSubmissionIntent() === "feedback" && latestSubmissionStatus() === "failed") {
      return "Entwurf vorhanden, Rückmeldung fehlgeschlagen";
    }
    if (latestSubmissionIntent() === "feedback") {
      return "Entwurf wird ausgewertet";
    }
    return "Noch nicht abgegeben";
  }

  function statusDetail(): string | null {
    if (hasFinalSubmission() && latestSubmissionIntent() === "feedback") {
      if (latestSubmissionStatus() === "completed") {
        return "Ein neuer Entwurf mit Rückmeldung liegt bereits vor.";
      }
      if (latestSubmissionStatus() === "pending" || latestSubmissionStatus() === "extracted") {
        return "Ein neuer Entwurf wird gerade ausgewertet.";
      }
    }
    return null;
  }

  function updateDraft(value: string) {
    draftText = value;
  }

  function compactTaskTone(): CompactTaskTone {
    if (hasFinalSubmission()) {
      return "final";
    }
    if (latestSubmissionIntent() === "feedback" && latestSubmissionStatus() === "failed") {
      return "error";
    }
    if (latestSubmissionIntent() === "feedback" && latestSubmissionStatus() === "completed") {
      return "draft";
    }
    if (latestSubmissionIntent() === "feedback") {
      return "pending";
    }
    return "new";
  }

  function compactRowActive(): boolean {
    return submissionFocused || reviewPanelOpen;
  }

  $effect(() => {
    if (!reviewPanelOpen) {
      activeSummaryTab = "submission";
    }
  });

  $effect(() => {
    if (submissionFocused && !lastSubmissionFocused) {
      editorMode = preferredEditorMode();
      selectedUploadFile = null;
      hideExistingUpload = false;
      if (uploadInput) {
        uploadInput.value = "";
      }
    }
    lastSubmissionFocused = submissionFocused;
  });

</script>

<article
  class:learning-work-item--collapsed={!expanded && !usesCompactTaskLayout()}
  class:learning-work-item--task-compact={usesCompactTaskLayout()}
  class="learning-work-item learning-work-item--task"
  id={domId}
>
  {#if usesCompactTaskLayout()}
    <section
      class:learning-task-row--active={compactRowActive()}
      class:learning-task-row--draft={compactTaskTone() === "draft"}
      class:learning-task-row--error={compactTaskTone() === "error"}
      class:learning-task-row--final={compactTaskTone() === "final"}
      class:learning-task-row--new={compactTaskTone() === "new"}
      class:learning-task-row--pending={compactTaskTone() === "pending"}
      class="learning-task-row"
      aria-label={taskPreviewLine()}
    >
      <div class="learning-task-row__copy">
        <p class="learning-task-row__preview">{taskPreviewLine()}</p>
      </div>

      <div class="learning-task-row__actions">
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
          class:workspace-top-action--active={submissionFocused}
          class:workspace-top-action--accent={!hasSubmission()}
          class:workspace-top-action--quiet={hasSubmission()}
          class="workspace-top-action"
          type="button"
          onclick={() => {
            if (uploadOnly() || preferredEditorMode() === "upload") {
              onEnterUploadWorkspace?.();
              return;
            }
            onEnterSubmissionWorkspace?.();
          }}
        >
          {actionLabel()}
        </button>
        {#if task.kind !== "h5p" && canFinalizeLatestDraft()}
          <form method="POST" use:enhance={enhanceSubmit}>
            <input type="hidden" name="task_id" value={task.id} />
            <input type="hidden" name="task_kind" value={task.kind} />
            <input type="hidden" name="unit_type" value={unitType} />
            {#if moduleId}
              <input type="hidden" name="module_id" value={moduleId} />
            {/if}
            <button
              class="workspace-top-action workspace-top-action--accent"
              name="submission_intent"
              type="submit"
              value="submit"
              disabled={feedbackPending}
            >
              Endgültig abgeben
            </button>
          </form>
        {/if}
      </div>
    </section>
  {:else}
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
  {/if}

    {#if expanded || usesCompactTaskLayout()}
      <div class="learning-work-item__body">
        {#if !usesCompactTaskLayout()}
          <div class="markdown-prose">
            {@html renderMarkdown(task.instruction_md)}
          </div>

          {#if task.kind !== "h5p"}
            <section class="learning-task-status" aria-label="Aufgabenstatus">
              <p class="workspace-label">Status</p>
              <p class="learning-task-status__headline">{statusHeadline()}</p>
              {#if statusDetail()}
                <p class="learning-task-status__detail">{statusDetail()}</p>
              {/if}
            </section>
          {/if}
        {/if}

        {#if submissionFocused}
          <section class="learning-task-inline-editor">
            <header class="learning-task-inline-editor__header">
              <div>
                <h5 class="learning-task-inline-editor__title">{taskTitle}</h5>
                {#if usesCompactTaskLayout()}
                  <div class="markdown-prose learning-task-inline-editor__statement">
                    {@html renderMarkdown(task.instruction_md)}
                  </div>
                {:else}
                  <p class="learning-task-inline-editor__copy">Die Bearbeitung bleibt Teil derselben Arbeitsfläche.</p>
                {/if}
              </div>
              <button
                class="workspace-top-action workspace-top-action--quiet workspace-top-action--subtle"
                type="button"
                onclick={() => onExitSubmissionWorkspace?.()}
              >
                Pausieren
              </button>
            </header>

            {#if showInlinePendingNote()}
              <p class="workspace-note">{feedbackPendingMessage()}</p>
            {/if}

            {#if task.kind === "h5p"}
              {#if task.h5p?.content_id}
                <H5PTaskPlayer {courseId} taskId={task.id} contentId={task.h5p.content_id} {onProgressPersisted} />
              {:else}
                <p class="workspace-note">Diese H5P-Aufgabe ist noch nicht bereit.</p>
              {/if}
            {:else if editorMode === "upload" || uploadOnly()}
              <form class="learning-submission-upload" method="POST" enctype="multipart/form-data" use:enhance={enhanceSubmit}>
                <input type="hidden" name="task_id" value={task.id} />
                <input type="hidden" name="task_kind" value={task.kind} />
                <input type="hidden" name="unit_type" value={unitType} />
                {#if moduleId}
                  <input type="hidden" name="module_id" value={moduleId} />
                {/if}
                {#if !uploadOnly()}
                  <div class="learning-submission-workspace__mode-switch learning-task-inline-editor__mode-switch" role="tablist" aria-label="Bearbeitungsmodus">
                    <button
                      class:workspace-tab--active={editorModeIs("text")}
                      class="workspace-tab"
                      type="button"
                      onclick={() => setEditorMode("text")}
                    >
                      Text
                    </button>
                    <button
                      class:workspace-tab--active={editorModeIs("upload")}
                      class="workspace-tab"
                      type="button"
                      onclick={() => setEditorMode("upload")}
                    >
                      Upload
                    </button>
                  </div>
                {/if}
                <label class="learning-submission-upload__dropzone">
                  <span class="learning-submission-upload__title">{uploadTitle()}</span>
                  <span class="learning-submission-upload__copy">{uploadCopy()}</span>
                  <input
                    bind:this={uploadInput}
                    aria-label="Datei auswählen"
                    name="upload_file"
                    type="file"
                    accept={uploadAccept()}
                    onchange={handleUploadSelection}
                  />
                </label>
                {#if selectedUploadFile}
                  <section class="learning-submission-upload__selected" aria-label="Ausgewählte Datei">
                    <div>
                      <p class="learning-submission-upload__selected-name">{selectedUploadFile.name}</p>
                      <p class="learning-submission-upload__selected-meta">{selectedUploadLabel(selectedUploadFile)}</p>
                    </div>
                    <div class="learning-submission-upload__selected-actions">
                      <button
                        class="workspace-top-action workspace-top-action--quiet workspace-top-action--subtle"
                        type="button"
                        onclick={clearUploadSelection}
                      >
                        Entfernen
                      </button>
                    </div>
                  </section>
                {:else if currentUploadSubmission()}
                  <section class="learning-submission-upload__selected" aria-label="Bisherige Datei">
                    <div>
                      <p class="learning-submission-upload__selected-name">Bisherige Datei</p>
                      <p class="learning-submission-upload__selected-meta">{fileSummary(currentUploadSubmission()!)}</p>
                    </div>
                    <div class="learning-submission-upload__selected-actions">
                      <button
                        class="workspace-top-action workspace-top-action--quiet workspace-top-action--subtle"
                        type="button"
                        onclick={clearUploadSelection}
                      >
                        Entfernen
                      </button>
                    </div>
                  </section>
                {/if}
                <div class="learning-submission-editor__actions">
                  <button
                    class="workspace-top-action workspace-top-action--quiet"
                    name="submission_intent"
                    type={onSubmitUploadFeedback ? "button" : "submit"}
                    value="feedback"
                    disabled={feedbackPending || !hasUploadReadyForSubmit()}
                    onclick={() => {
                      if (onSubmitUploadFeedback) {
                        submitUploadFeedback();
                      }
                    }}
                  >
                    Rückmeldung einholen
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
                <div class="learning-submission-workspace__mode-switch learning-task-inline-editor__mode-switch" role="tablist" aria-label="Bearbeitungsmodus">
                  <button
                    class:workspace-tab--active={editorModeIs("text")}
                    class="workspace-tab"
                    type="button"
                    onclick={() => setEditorMode("text")}
                  >
                    Text
                  </button>
                  <button
                    class:workspace-tab--active={editorModeIs("upload")}
                    class="workspace-tab"
                    type="button"
                    onclick={() => setEditorMode("upload")}
                  >
                    Upload
                  </button>
                </div>
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
          {#if !usesCompactTaskLayout()}
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
                class:workspace-top-action--accent={!hasSubmission()}
                class:workspace-top-action--quiet={hasSubmission()}
                class="workspace-top-action"
                type="button"
                onclick={() => {
                  if (uploadOnly() || preferredEditorMode() === "upload") {
                    onEnterUploadWorkspace?.();
                    return;
                  }
                  onEnterSubmissionWorkspace?.();
                }}
              >
                {actionLabel()}
              </button>
              {#if task.kind !== "h5p" && canFinalizeLatestDraft()}
                <form method="POST" use:enhance={enhanceSubmit}>
                  <input type="hidden" name="task_id" value={task.id} />
                  <input type="hidden" name="task_kind" value={task.kind} />
                  <input type="hidden" name="unit_type" value={unitType} />
                  {#if moduleId}
                    <input type="hidden" name="module_id" value={moduleId} />
                  {/if}
                  <button
                    class="workspace-top-action workspace-top-action--accent"
                    name="submission_intent"
                    type="submit"
                    value="submit"
                    disabled={feedbackPending}
                  >
                    Endgültig abgeben
                  </button>
                </form>
              {/if}
            </div>
          {/if}
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

              {#if usesCompactTaskLayout()}
                <div class="markdown-prose learning-task-inline-editor__statement">
                  {@html renderMarkdown(task.instruction_md)}
                </div>
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
                  {#if latestSubmission() && submittedArtifact()}
                    <LearningSubmissionArtifactView submission={latestSubmissionOrThrow()} />
                  {:else if latestSubmission() && latestSubmissionOrThrow().text_body}
                    <div class="markdown-prose">
                      {@html renderMarkdown(latestSubmissionOrThrow().text_body)}
                    </div>
                  {:else if submittedFile()?.mime.startsWith("image/")}
                    <div class="learning-task-submission-summary__asset">
                      <img alt="Abgabevorschau" class="learning-task-submission-summary__image" src={submittedFile()?.url} />
                      <p class="learning-task-submission-summary__asset-meta">{fileSummary(latestSubmissionOrThrow())}</p>
                      <a class="learning-work-item__link" href={submittedFile()?.url}>Datei öffnen</a>
                    </div>
                  {:else if submittedFile()?.mime === "application/pdf"}
                    <div class="learning-task-submission-summary__asset">
                      <iframe
                        class="learning-task-submission-summary__frame"
                        src={submittedFile()?.url}
                        title={`Abgabe ${latestSubmissionOrThrow().created_at}`}
                      ></iframe>
                      <p class="learning-task-submission-summary__asset-meta">{fileSummary(latestSubmissionOrThrow())}</p>
                      <a class="learning-work-item__link" href={submittedFile()?.url}>Datei öffnen</a>
                    </div>
                  {:else if submittedFile()}
                    <div class="learning-task-submission-summary__asset">
                      <p class="learning-task-submission-summary__plain">{fileSummary(latestSubmissionOrThrow())}</p>
                      <a class="learning-work-item__link" href={submittedFile()?.url}>Datei öffnen</a>
                    </div>
                  {:else if latestSubmission()}
                    <p class="learning-task-submission-summary__plain">{fileSummary(latestSubmissionOrThrow())}</p>
                  {:else if feedbackPending}
                    <p class="learning-task-submission-summary__plain">Die aktuelle Abgabe wird vorbereitet.</p>
                  {:else if historyStateMessage()}
                    <p class="learning-task-submission-summary__plain">{historyStateMessage()}</p>
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
                  {:else if historyStateMessage()}
                    <p class="learning-task-submission-summary__plain">{historyStateMessage()}</p>
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
                  {:else if historyStateMessage()}
                    <p class="learning-task-submission-summary__plain">{historyStateMessage()}</p>
                  {:else}
                    <p class="learning-task-submission-summary__plain">Es liegt noch keine Auswertung vor.</p>
                  {/if}
                {/if}
              </div>
            </section>
          {/if}
        {/if}
      </div>
    {/if}
</article>
