<script lang="ts">
  import { browser } from "$app/environment";
  import { enhance } from "$app/forms";
  import H5PTaskPlayer from "$lib/components/H5PTaskPlayer.svelte";
  import LearningDialogWorkspace from "$lib/components/learning-unit/LearningDialogWorkspace.svelte";
  import LearningSubmissionArtifactView from "$lib/components/learning-unit/LearningSubmissionArtifactView.svelte";
  import MarkdownWysiwygEditor from "$lib/components/ui/MarkdownEditor.svelte";
  import ChoiceSwitch from "$lib/components/ui/ChoiceSwitch.svelte";
  import StatusMessage, { type StatusMessageTone } from "$lib/components/ui/StatusMessage.svelte";
  import {
    legacySubmissionDraftStorageKey,
    submissionDraftStorageKey
  } from "$lib/learning-unit/submission-drafts";
  import { taskInstructionPreview, taskPreviewIsVisuallyClipped } from "$lib/learning-unit/task-preview";
  import { finalSubmissionIdempotencyKey } from "$lib/learning-unit/submission-finalization";
  import type { LearnerMaterialContextModule } from "$lib/learning-unit/workspace";
  import { buildSubmissionArtifactView } from "$lib/utils/submission-artifacts";
  import { renderMarkdown } from "$lib/utils/markdown";
  import type { LearningSubmission, LearningTask } from "$lib/types/learning";
  import type { SubmitFunction } from "@sveltejs/kit";
  import { onMount, untrack } from "svelte";

  let {
    learnerSub = null,
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
    compactLayout = false,
    workspaceOnly = false,
    dialogCompactSurface = "task",
    dialogExpandedModuleMaterialKeys = {},
    dialogExpandedContextModuleIds = [],
    dialogExpandedSubmissionModuleIds = [],
    dialogExpandedSubmissionKeys = [],
    dialogContextModules = [],
    dialogHistoryByTask = {},
    dialogHistoryStateByTask = {},
    dialogFocusedContextModuleId = null,
    dialogClosedContextModuleTitle = null,
    dialogTaskColumnRatio = null,
    hideDialogPauseAction = false,
    enhanceSubmit = undefined,
    onToggle = null,
    onDismissFeedbackStatus = null,
    onEnterSubmissionWorkspace = null,
    onEnterUploadWorkspace = null,
    onExitSubmissionWorkspace = null,
    onSetDialogCompactSurface = null,
    onPreviewDialogTaskColumnRatio = null,
    onCommitDialogTaskColumnRatio = null,
    onOpenDialogContext = null,
    onToggleDialogMaterial = null,
    onToggleDialogContextModule = null,
    onToggleDialogSubmissionGroup = null,
    onToggleDialogSubmission = null,
    onCloseDialogContextModule = null,
    onUndoCloseDialogContextModule = null,
    onSubmitUploadFeedback = null,
    onProgressPersisted = null
  }: {
    learnerSub?: string | null;
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
    compactLayout?: boolean;
    workspaceOnly?: boolean;
    dialogCompactSurface?: "task" | "materials";
    dialogExpandedModuleMaterialKeys?: Record<string, string[]>;
    dialogExpandedContextModuleIds?: string[];
    dialogExpandedSubmissionModuleIds?: string[];
    dialogExpandedSubmissionKeys?: string[];
    dialogContextModules?: LearnerMaterialContextModule[];
    dialogHistoryByTask?: Record<string, LearningSubmission[]>;
    dialogHistoryStateByTask?: Record<string, SubmissionHistoryLoadState>;
    dialogFocusedContextModuleId?: string | null;
    dialogClosedContextModuleTitle?: string | null;
    dialogTaskColumnRatio?: number | null;
    hideDialogPauseAction?: boolean;
    enhanceSubmit?: SubmitFunction;
    onToggle?: (() => void) | null;
    onDismissFeedbackStatus?: (() => void) | null;
    onEnterSubmissionWorkspace?: (() => void) | null;
    onEnterUploadWorkspace?: (() => void) | null;
    onExitSubmissionWorkspace?: (() => void) | null;
    onSetDialogCompactSurface?: ((surface: "task" | "materials") => void) | null;
    onPreviewDialogTaskColumnRatio?: ((value: number) => void) | null;
    onCommitDialogTaskColumnRatio?: ((value: number) => void) | null;
    onOpenDialogContext?: ((key: string) => void | Promise<void>) | null;
    onToggleDialogMaterial?: ((moduleId: string, key: string) => void) | null;
    onToggleDialogContextModule?: ((moduleId: string) => void | Promise<void>) | null;
    onToggleDialogSubmissionGroup?: ((moduleId: string) => void | Promise<void>) | null;
    onToggleDialogSubmission?: ((key: string) => void) | null;
    onCloseDialogContextModule?: ((moduleId: string) => void) | null;
    onUndoCloseDialogContextModule?: (() => void) | null;
    onSubmitUploadFeedback?: ((payload: {
      taskId: string;
      taskKind: UploadTaskKind;
      file: File;
      moduleId: string | null;
    }) => void | Promise<void>) | null;
    onProgressPersisted?: ((submission?: LearningSubmission | null) => void | Promise<void>) | null;
  } = $props();

  type SubmissionMode = "text" | "upload";
  type SubmissionHistoryLoadState = "not_loaded" | "loading" | "loaded" | "failed" | "unavailable";
  type UploadTaskKind = Extract<LearningTask["kind"], "native" | "visual" | "scratch" | "calliope" | "filius">;
  type CompactTaskTone = "new" | "draft" | "pending" | "final" | "error";
  const DRAFT_PERSIST_DELAY_MS = 200;
  let draftText = $state("");
  let editorMode = $state<SubmissionMode>("text");
  let selectedUploadFile = $state<File | null>(null);
  let hideExistingUpload = $state(false);
  let uploadInput = $state<HTMLInputElement | null>(null);
  let lastSubmissionFocused = $state(false);
  let lastWorkspaceTaskId = $state<string | null>(null);
  let lastFeedbackPending = $state(false);
  let lastReviewPanelOpen = $state(untrack(() => reviewPanelOpen));
  let feedbackDisclosureOpen = $state(false);
  let submissionDisclosureOpen = $state(untrack(() => reviewPanelOpen));
  let taskPreviewVisuallyClipped = $state(false);
  let pendingDraftWrite: { key: string; value: string } | null = null;
  let draftPersistTimer: ReturnType<typeof setTimeout> | null = null;

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

  function taskPreview() {
    return taskInstructionPreview(task.instruction_md, taskTitle);
  }

  function observeTaskPreview(node: HTMLElement, _previewText: string) {
    const measure = () => {
      taskPreviewVisuallyClipped = taskPreviewIsVisuallyClipped(node.scrollHeight, node.clientHeight);
    };
    const resizeObserver = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    resizeObserver?.observe(node);
    window.addEventListener("resize", measure);
    queueMicrotask(measure);

    return {
      update() {
        queueMicrotask(measure);
      },
      destroy() {
        resizeObserver?.disconnect();
        window.removeEventListener("resize", measure);
      }
    };
  }

  function usesCompactTaskLayout(): boolean {
    return compactLayout;
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

  function legacyDraftStorageKey(mode: SubmissionMode = editorMode): string {
    return legacySubmissionDraftStorageKey({ courseId, taskId: task.id, mode });
  }

  function scopedDraftStorageKey(mode: SubmissionMode = editorMode): string | null {
    return submissionDraftStorageKey({ learnerSub, courseId, taskId: task.id, mode });
  }

  function removeLegacyDraft(mode: SubmissionMode = editorMode) {
    const key = legacyDraftStorageKey(mode);
    window.localStorage.removeItem(key);
    window.sessionStorage.removeItem(key);
  }

  function persistPendingDraft() {
    if (draftPersistTimer !== null) {
      clearTimeout(draftPersistTimer);
      draftPersistTimer = null;
    }
    if (!browser || !pendingDraftWrite) {
      return;
    }
    const { key, value } = pendingDraftWrite;
    pendingDraftWrite = null;
    window.localStorage.removeItem(key);
    window.sessionStorage.setItem(key, value);
  }

  /**
   * Keep keystrokes off synchronous Web Storage while retaining the newest complete draft.
   * The pending write is flushed before submit, navigation, task changes, and component teardown.
   */
  function scheduleDraftPersistence(key: string, value: string) {
    pendingDraftWrite = { key, value };
    if (draftPersistTimer !== null) {
      clearTimeout(draftPersistTimer);
    }
    draftPersistTimer = setTimeout(persistPendingDraft, DRAFT_PERSIST_DELAY_MS);
  }

  function restoreDraft(mode: SubmissionMode = editorMode) {
    if (!browser || uploadOnly() || mode !== "text") {
      return;
    }
    persistPendingDraft();
    removeLegacyDraft(mode);
    const key = scopedDraftStorageKey(mode);
    if (key) {
      window.localStorage.removeItem(key);
    }
    const storedDraft = key ? window.sessionStorage.getItem(key) : null;
    draftText = storedDraft ?? (latestSubmission()?.kind === "text" ? latestSubmission()?.text_body ?? "" : "");
  }

  function setEditorMode(next: SubmissionMode) {
    editorMode = next;
    if (next === "text") {
      restoreDraft(next);
    }
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

  function hasEvaluation(submission: LearningSubmission): boolean {
    return Boolean(submission.analysis_json?.criteria_results?.length);
  }

  function hasInlineResponse(): boolean {
    const submission = latestSubmission();
    return Boolean(submission && task.kind !== "dialog" && task.kind !== "h5p");
  }

  function canOfferFinalization(): boolean {
    const submission = latestSubmission();
    return Boolean(
      submission &&
      submission.intent === "feedback" &&
      submission.analysis_status === "completed"
    );
  }

  function currentFinalizationIdempotencyKey(): string | null {
    return canOfferFinalization() ? finalSubmissionIdempotencyKey(latestSubmission()?.id) : null;
  }

  function currentDraftMatchesFeedback(): boolean {
    const submission = latestSubmission();
    if (!submission || !canOfferFinalization()) {
      return false;
    }
    if (editorMode === "text") {
      return submission.kind === "text" && draftText.trim() === (submission.text_body ?? "").trim();
    }
    return isUploadSubmission(submission) && !selectedUploadFile && !hideExistingUpload;
  }

  function editingLocked(): boolean {
    return feedbackPending || (reviewPanelOpen && hasFinalSubmission());
  }

  function feedbackActionLabel(): string {
    return canOfferFinalization() ? "Rückmeldung erneut einholen" : "Rückmeldung einholen";
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

  function feedbackMessageTone(): StatusMessageTone {
    if (feedbackPending) {
      return feedbackStatusMessage?.includes("dauert länger") ? "warning" : "progress";
    }
    if (message === "feedback" || message === "submitted") {
      return "success";
    }
    if (feedbackStatusMessage === "Die Abgabe wird geladen ...") {
      return "progress";
    }
    return "error";
  }

  function feedbackMessageDescription(): string | null {
    const tone = feedbackMessageTone();
    if (tone === "progress") {
      return "Du kannst währenddessen in GUSTAV weiterarbeiten.";
    }
    if (tone === "warning") {
      return "Du musst nichts erneut abgeben. GUSTAV prüft den Stand weiter.";
    }
    return null;
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
    if (!browser || uploadOnly() || editorMode !== "text") {
      return;
    }
    const key = scopedDraftStorageKey("text");
    if (!key) {
      return;
    }
    scheduleDraftPersistence(key, value);
  }

  onMount(() => {
    window.addEventListener("pagehide", persistPendingDraft);
    return () => {
      window.removeEventListener("pagehide", persistPendingDraft);
      persistPendingDraft();
    };
  });

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
    const workspaceActive = submissionFocused || reviewPanelOpen;
    const workspaceTaskChanged = workspaceActive && lastWorkspaceTaskId !== null && lastWorkspaceTaskId !== task.id;
    if (workspaceActive && (!lastSubmissionFocused || workspaceTaskChanged)) {
      const nextMode = preferredEditorMode();
      editorMode = nextMode;
      if (nextMode === "text") {
        restoreDraft(nextMode);
      }
      selectedUploadFile = null;
      hideExistingUpload = false;
      if (uploadInput) {
        uploadInput.value = "";
      }
    }
    lastSubmissionFocused = workspaceActive;
    lastWorkspaceTaskId = workspaceActive ? task.id : null;
  });

  $effect(() => {
    if (lastFeedbackPending && !feedbackPending && message === "feedback") {
      feedbackDisclosureOpen = true;
      selectedUploadFile = null;
      hideExistingUpload = false;
      if (uploadInput) {
        uploadInput.value = "";
      }
    }
    lastFeedbackPending = feedbackPending;
  });

  $effect(() => {
    if (reviewPanelOpen && !lastReviewPanelOpen) {
      submissionDisclosureOpen = true;
    }
    lastReviewPanelOpen = reviewPanelOpen;
  });

</script>

<article
  class:learning-work-item--collapsed={!expanded && !usesCompactTaskLayout()}
  class:learning-work-item--task-compact={usesCompactTaskLayout()}
  class:learning-work-item--workspace-only={workspaceOnly}
  class="learning-work-item learning-work-item--task"
  id={domId}
>
  {#if !workspaceOnly && usesCompactTaskLayout()}
    <section
      class:learning-task-row--active={compactRowActive()}
      class:learning-task-row--draft={compactTaskTone() === "draft"}
      class:learning-task-row--error={compactTaskTone() === "error"}
      class:learning-task-row--final={compactTaskTone() === "final"}
      class:learning-task-row--new={compactTaskTone() === "new"}
      class:learning-task-row--pending={compactTaskTone() === "pending"}
      class="learning-task-row"
      aria-label={taskPreview().text}
    >
      <div class="learning-task-row__copy">
        <p class="learning-task-row__preview" use:observeTaskPreview={taskPreview().text}>{taskPreview().text}</p>
        {#if taskPreview().truncated || taskPreviewVisuallyClipped}
          <p class="learning-task-row__more">Weitere Angaben in der Aufgabe</p>
        {/if}
      </div>

      <div class="learning-task-row__actions">
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
      </div>
    </section>
  {:else if !workspaceOnly}
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

    {#if workspaceOnly || expanded || usesCompactTaskLayout()}
      <div class="learning-work-item__body">
        {#if workspaceOnly}
          <section class="learning-task-workspace-statement" aria-label="Vollständige Aufgabenstellung">
            <p class="workspace-label">Vollständige Aufgabe</p>
            <div class="markdown-prose">
              {@html renderMarkdown(task.instruction_md)}
            </div>
          </section>
        {/if}

        {#if feedbackPendingMessage()}
          <div
            class:learning-task-feedback-status--active={submissionFocused || workspaceOnly}
            class="learning-task-feedback-status"
          >
            <StatusMessage
              tone={feedbackMessageTone()}
              title={feedbackPendingMessage()!}
              description={feedbackMessageDescription()}
              onDismiss={onDismissFeedbackStatus}
              dismissible={feedbackMessageTone() === "error"}
            />
          </div>
        {/if}

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

        {#if submissionFocused || reviewPanelOpen}
          <section class="learning-task-inline-editor">
            {#if !workspaceOnly}
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
              {#if task.kind !== "dialog" && !reviewPanelOpen}
                <button
                  class="workspace-top-action workspace-top-action--quiet workspace-top-action--subtle"
                  type="button"
                  onclick={() => onExitSubmissionWorkspace?.()}
                >
                  Pausieren
                </button>
              {/if}
              </header>
            {/if}

            {#if hasInlineResponse()}
              <section class="learning-task-inline-response" aria-label="Rückmeldung zu deiner Abgabe">
                <p class="learning-task-inline-response__meta">
                  Zu deiner Abgabe · {latestSubmissionOrThrow().created_at}
                </p>

                <div class="learning-response-group">
                  {#if latestSubmissionOrThrow().feedback_md}
                    <details class="learning-response-panel" bind:open={feedbackDisclosureOpen}>
                      <summary>Rückmeldung</summary>
                      <div class="learning-response-panel__body markdown-prose">
                        {@html renderMarkdown(latestSubmissionOrThrow().feedback_md ?? "")}
                      </div>
                    </details>
                  {/if}

                  {#if hasEvaluation(latestSubmissionOrThrow())}
                    <details class="learning-response-panel">
                      <summary>Auswertung</summary>
                      <div class="learning-response-panel__body">
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
                      </div>
                    </details>
                  {/if}

                  <details class="learning-response-panel" bind:open={submissionDisclosureOpen}>
                    <summary>Meine Abgabe</summary>
                    <div class="learning-response-panel__body">
                      {#if submittedFile()?.mime.startsWith("image/")}
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
                      {:else if submittedArtifact()}
                        <LearningSubmissionArtifactView submission={latestSubmissionOrThrow()} />
                      {:else if submittedFile()}
                        <div class="learning-task-submission-summary__asset">
                          <p class="learning-task-submission-summary__plain">{fileSummary(latestSubmissionOrThrow())}</p>
                          <a class="learning-work-item__link" href={submittedFile()?.url}>Datei öffnen</a>
                        </div>
                      {:else if latestSubmissionOrThrow().text_body}
                        <div class="markdown-prose">
                          {@html renderMarkdown(latestSubmissionOrThrow().text_body ?? "")}
                        </div>
                      {/if}
                    </div>
                  </details>
                </div>
              </section>
            {/if}

            {#if task.kind === "dialog"}
              <LearningDialogWorkspace
                {learnerSub}
                {courseId}
                {task}
                {taskTitle}
                compactSurface={dialogCompactSurface}
                expandedModuleMaterialKeys={dialogExpandedModuleMaterialKeys}
                expandedContextModuleIds={dialogExpandedContextModuleIds}
                expandedSubmissionModuleIds={dialogExpandedSubmissionModuleIds}
                expandedSubmissionKeys={dialogExpandedSubmissionKeys}
                contextModules={dialogContextModules}
                historyByTask={dialogHistoryByTask}
                historyStateByTask={dialogHistoryStateByTask}
                focusedContextModuleId={dialogFocusedContextModuleId}
                closedContextModuleTitle={dialogClosedContextModuleTitle}
                taskColumnRatio={dialogTaskColumnRatio}
                onSetCompactSurface={onSetDialogCompactSurface}
                onPreviewTaskColumnRatio={onPreviewDialogTaskColumnRatio}
                onCommitTaskColumnRatio={onCommitDialogTaskColumnRatio}
                onOpenContext={onOpenDialogContext}
                onToggleContextMaterial={onToggleDialogMaterial}
                onToggleContextModule={onToggleDialogContextModule}
                onToggleSubmissionGroup={onToggleDialogSubmissionGroup}
                onToggleSubmission={onToggleDialogSubmission}
                onCloseContextModule={onCloseDialogContextModule}
                onUndoCloseContextModule={onUndoCloseDialogContextModule}
                onPause={onExitSubmissionWorkspace}
                showPauseAction={!hideDialogPauseAction}
                onCompleted={onProgressPersisted}
              />
            {:else if task.kind === "h5p"}
              {#if task.h5p?.content_id}
                <H5PTaskPlayer {courseId} taskId={task.id} contentId={task.h5p.content_id} {onProgressPersisted} />
              {:else}
                <p class="workspace-note">Diese H5P-Aufgabe ist noch nicht bereit.</p>
              {/if}
            {:else}
              {#if !uploadOnly()}
                <ChoiceSwitch
                  legend="Antwortform"
                  name={`answer-mode-${task.id}`}
                  value={editorMode}
                  options={[
                    { value: "text", label: "Text schreiben", disabled: editingLocked() },
                    { value: "upload", label: "Datei hochladen", disabled: editingLocked() }
                  ]}
                  onValueChange={(value) => setEditorMode(value as SubmissionMode)}
                />
              {/if}

              {#if !uploadOnly()}
                <div class="learning-submission-mode-panel" hidden={editorMode !== "text"}>
                  <form class="learning-submission-editor learning-submission-editor--immersive" method="POST" enctype="multipart/form-data" onsubmit={persistPendingDraft} use:enhance={enhanceSubmit}>
                    <input type="hidden" name="task_id" value={task.id} />
                    <input type="hidden" name="task_kind" value={task.kind} />
                    <input type="hidden" name="unit_type" value={unitType} />
                    {#if moduleId}
                      <input type="hidden" name="module_id" value={moduleId} />
                    {/if}
                    {#if currentFinalizationIdempotencyKey()}
                      <input type="hidden" name="feedback_submission_id" value={latestSubmission()?.id ?? ""} />
                      <input type="hidden" name="finalization_idempotency_key" value={currentFinalizationIdempotencyKey() ?? ""} />
                    {/if}
                    <section class="learning-submission-editor__field">
                      <span>Deine Lösung</span>
                      <MarkdownWysiwygEditor
                        name="text_body"
                        value={draftText}
                        placeholder="Schreibe hier deine Lösung."
                        disabled={editingLocked()}
                        onInput={updateDraft}
                      />
                    </section>
                    <div class="learning-submission-editor__actions">
                      <button class="workspace-top-action workspace-top-action--quiet" name="submission_intent" type="submit" value="feedback" disabled={editingLocked()}>
                        {feedbackActionLabel()}
                      </button>
                      {#if canOfferFinalization()}
                        <button
                          class="workspace-top-action workspace-top-action--accent"
                          name="submission_intent"
                          type="submit"
                          value="submit"
                          disabled={editingLocked() || !currentDraftMatchesFeedback()}
                        >
                          Endgültig abgeben
                        </button>
                      {/if}
                    </div>
                    {#if canOfferFinalization()}
                      <p class="learning-submission-editor__final-hint">
                        {currentDraftMatchesFeedback()
                          ? "Diese Fassung kann endgültig abgegeben werden."
                          : "Für diese Fassung zuerst Rückmeldung einholen."}
                      </p>
                    {/if}
                  </form>
                </div>
              {/if}

              <div class="learning-submission-mode-panel" hidden={!uploadOnly() && editorMode !== "upload"}>
                <form class="learning-submission-upload" method="POST" enctype="multipart/form-data" use:enhance={enhanceSubmit}>
                  <input type="hidden" name="task_id" value={task.id} />
                  <input type="hidden" name="task_kind" value={task.kind} />
                  <input type="hidden" name="unit_type" value={unitType} />
                  {#if moduleId}
                    <input type="hidden" name="module_id" value={moduleId} />
                  {/if}
                  {#if currentFinalizationIdempotencyKey()}
                    <input type="hidden" name="feedback_submission_id" value={latestSubmission()?.id ?? ""} />
                    <input type="hidden" name="finalization_idempotency_key" value={currentFinalizationIdempotencyKey() ?? ""} />
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
                      disabled={editingLocked()}
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
                          disabled={editingLocked()}
                          onclick={clearUploadSelection}
                        >
                          Entfernen
                        </button>
                      </div>
                    </section>
                  {:else if currentUploadSubmission()}
                    <section class="learning-submission-upload__selected" aria-label="Bisherige Datei">
                      <div>
                        <p class="learning-submission-upload__selected-name">Aktuelle Datei</p>
                        <p class="learning-submission-upload__selected-meta">{fileSummary(currentUploadSubmission()!)}</p>
                      </div>
                      <div class="learning-submission-upload__selected-actions">
                        <button
                          class="workspace-top-action workspace-top-action--quiet workspace-top-action--subtle"
                          type="button"
                          disabled={editingLocked()}
                          onclick={triggerUploadPicker}
                        >
                          Andere Datei auswählen
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
                      disabled={editingLocked() || !hasUploadReadyForSubmit()}
                      onclick={() => {
                        if (onSubmitUploadFeedback) {
                          submitUploadFeedback();
                        }
                      }}
                    >
                      {feedbackActionLabel()}
                    </button>
                    {#if canOfferFinalization()}
                      <button
                        class="workspace-top-action workspace-top-action--accent"
                        name="submission_intent"
                        type="submit"
                        value="submit"
                        disabled={editingLocked() || !currentDraftMatchesFeedback()}
                      >
                        Endgültig abgeben
                      </button>
                    {/if}
                  </div>
                  {#if canOfferFinalization()}
                    <p class="learning-submission-editor__final-hint">
                      {currentDraftMatchesFeedback()
                        ? "Diese Fassung kann endgültig abgegeben werden."
                        : "Für diese Fassung zuerst Rückmeldung einholen."}
                    </p>
                  {/if}
                </form>
              </div>
            {/if}

            {#if errorMessage}
              <StatusMessage tone="error" title="Abgabe nicht möglich" description={errorMessage} focusOnMount={true} />
            {/if}
          </section>
        {:else}
          {#if !usesCompactTaskLayout()}
            <div class="learning-task-cta-row">
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
            </div>
          {/if}
        {/if}
      </div>
    {/if}
</article>
