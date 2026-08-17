<script lang="ts">
  import { browser } from "$app/environment";
  import { onMount } from "svelte";

  import LearningSubmissionArtifactView from "$lib/components/learning-unit/LearningSubmissionArtifactView.svelte";
  import MarkdownWysiwygEditor from "$lib/components/ui/MarkdownEditor.svelte";
  import ChoiceSwitch from "$lib/components/ui/ChoiceSwitch.svelte";
  import StatusMessage from "$lib/components/ui/StatusMessage.svelte";
  import {
    legacySubmissionDraftStorageKey,
    submissionDraftStorageKey
  } from "$lib/learning-unit/submission-drafts";
  import { buildSubmissionArtifactView } from "$lib/utils/submission-artifacts";
  import { learningSubmissionFailureMessage } from "$lib/utils/learning-failures";
  import {
    buildLearningSubmissionHistoryUrl,
    MISSING_SUBMISSION_HISTORY_CONTEXT_MESSAGE
  } from "$lib/utils/learning-submission-history-url";
  import { renderMarkdown } from "$lib/utils/markdown";
  import type { LearningSubmission, LearningTask } from "$lib/types/learning";

  type WorkspaceTab = "submit" | "history";
  type SubmissionMode = "text" | "upload";

  let {
    learnerSub = null,
    courseId,
    task,
    taskTitle = "Aufgabe",
    unitType,
    moduleId = null,
    initialHistory = [],
    initialHistoryLoaded = false,
    initialTab = "submit",
    initialMode = null,
    submitted = false,
    message = null,
    errorMessage = null,
    onClose = null
  }: {
    learnerSub?: string | null;
    courseId: string;
    task: LearningTask;
    taskTitle?: string;
    unitType: "linear" | "modular";
    moduleId?: string | null;
    initialHistory?: LearningSubmission[];
    initialHistoryLoaded?: boolean;
    initialTab?: WorkspaceTab;
    initialMode?: SubmissionMode | null;
    submitted?: boolean;
    message?: string | null;
    errorMessage?: string | null;
    onClose?: (() => void) | null;
  } = $props();

  let activeTab = $state<WorkspaceTab>("submit");
  let mode = $state<SubmissionMode>(uploadOnly() ? "upload" : "text");
  let draftText = $state("");
  let historyEntries = $state<LearningSubmission[]>([]);
  let historyLoaded = $state(false);
  let historyLoading = $state(false);
  let historyError = $state<string | null>(null);

  function uploadOnly(): boolean {
    return task.kind === "visual" || task.kind === "scratch" || task.kind === "calliope" || task.kind === "filius";
  }

  function legacyStorageKey(): string {
    return legacySubmissionDraftStorageKey({ courseId, taskId: task.id, mode });
  }

  function scopedStorageKey(): string | null {
    return submissionDraftStorageKey({ learnerSub, courseId, taskId: task.id, mode });
  }

  function removeLegacyDraft() {
    const key = legacyStorageKey();
    window.localStorage.removeItem(key);
    window.sessionStorage.removeItem(key);
  }

  function restoreDraft() {
    if (!browser || uploadOnly() || mode !== "text") {
      return;
    }
    removeLegacyDraft();
    const key = scopedStorageKey();
    if (key) {
      window.localStorage.removeItem(key);
    }
    draftText = key ? window.sessionStorage.getItem(key) ?? "" : "";
  }

  async function loadHistory() {
    if (!browser || historyLoading || historyLoaded) {
      return;
    }
    historyLoading = true;
    historyError = null;
    try {
      const historyUrl = buildLearningSubmissionHistoryUrl(courseId, task.id);
      if (!historyUrl) {
        historyError = MISSING_SUBMISSION_HISTORY_CONTEXT_MESSAGE;
        return;
      }
      const response = await fetch(historyUrl, {
        credentials: "include",
        cache: "no-store"
      });
      if (!response.ok) {
        throw new Error(`history_failed_${response.status}`);
      }
      historyEntries = (await response.json()) as LearningSubmission[];
      historyLoaded = true;
    } catch {
      historyError = "Der Verlauf konnte nicht geladen werden.";
    } finally {
      historyLoading = false;
    }
  }

  function setTab(next: WorkspaceTab) {
    activeTab = next;
    if (next === "history") {
      void loadHistory();
    }
  }

  function setMode(next: SubmissionMode) {
    mode = next;
    if (next === "text") {
      restoreDraft();
    }
  }

  function updateDraft(value: string) {
    draftText = value;
    if (!browser || uploadOnly() || mode !== "text") {
      return;
    }
    removeLegacyDraft();
    const key = scopedStorageKey();
    if (!key) {
      return;
    }
    window.localStorage.removeItem(key);
    window.sessionStorage.setItem(key, value);
  }

  function humanStatus(submission: LearningSubmission): string {
    if (submission.kind === "h5p" && submission.score_raw !== null && submission.score_raw !== undefined) {
      return `${submission.analysis_status} · ${submission.score_raw}/${submission.score_max ?? 0}`;
    }
    return submission.analysis_status;
  }

  function humanIntent(submission: LearningSubmission): string {
    return submission.intent === "feedback" ? "Rückmeldung" : "Abgabe";
  }

  function fileEntry(submission: LearningSubmission): { mime: string; size: number; url: string } | null {
    return submission.files?.[0] ?? null;
  }

  function artifactEntry(submission: LearningSubmission) {
    return buildSubmissionArtifactView(submission);
  }

  function formatBytes(size: number | null | undefined): string {
    if (!size || size <= 0) {
      return "Datei";
    }
    if (size < 1024 * 1024) {
      return `${Math.round(size / 1024)} KB`;
    }
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  }

  function latestFeedbackSubmission(): LearningSubmission | null {
    return historyEntries.find((submission) => submission.intent === "feedback" && Boolean(submission.feedback_md)) ?? null;
  }

  onMount(() => {
    activeTab = initialTab;
    if (initialMode === "text" || initialMode === "upload") {
      mode = initialMode;
    }
    historyEntries = [...initialHistory];
    historyLoaded = initialHistoryLoaded;
    if (submitted || errorMessage) {
      activeTab = submitted ? "history" : "submit";
    }
    restoreDraft();
    if (activeTab === "history" && !historyLoaded) {
      void loadHistory();
    }
  });
</script>

<section class:learning-submission-workspace--writing={activeTab === "submit" && mode === "text"} class="learning-submission-workspace">
  <header class="learning-submission-workspace__header">
    <div class="learning-submission-workspace__copy">
      <div class="learning-submission-workspace__eyebrow">
        <p class="workspace-label">Arbeitsbereich</p>
        <p class="learning-submission-workspace__meta">
        {#if uploadOnly()}
          Upload
        {:else}
          Schreiben und Abgeben
        {/if}
        </p>
      </div>
      <h5>{taskTitle}</h5>
    </div>

    <button class="workspace-top-action workspace-top-action--quiet" type="button" onclick={() => onClose?.()}>
      Zurück
    </button>
  </header>

  <div class="learning-submission-workspace__tabs">
    <button
      class:workspace-tab--active={activeTab === "submit"}
      class="workspace-tab"
      type="button"
      onclick={() => setTab("submit")}
    >
      Bearbeiten
    </button>
    <button
      class:workspace-tab--active={activeTab === "history"}
      class="workspace-tab"
      type="button"
      onclick={() => setTab("history")}
    >
      Verlauf &amp; Rückmeldung
    </button>
  </div>

  {#if activeTab === "submit"}
    <div class="learning-submission-workspace__body">
      {#if errorMessage}
        <StatusMessage tone="error" title="Abgabe nicht möglich" description={errorMessage} focusOnMount={true} />
      {/if}

      {#if !uploadOnly()}
        <ChoiceSwitch
          legend="Antwortform"
          name={`answer-mode-${task.id}`}
          value={mode}
          options={[
            { value: "text", label: "Text schreiben" },
            { value: "upload", label: "Datei hochladen" }
          ]}
          onValueChange={(value) => setMode(value as SubmissionMode)}
        />
      {/if}

      {#if !uploadOnly()}
        <div class="learning-submission-mode-panel" hidden={mode !== "text"}>
          <form method="POST" class="learning-submission-editor learning-submission-editor--immersive" enctype="multipart/form-data">
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
              <button class="workspace-top-action workspace-top-action--quiet" name="submission_intent" type="submit" value="feedback">
                Rückmeldung einholen
              </button>
              <button class="workspace-top-action workspace-top-action--accent" name="submission_intent" type="submit" value="submit">
                Endgültig abgeben
              </button>
            </div>
          </form>
        </div>
      {/if}

      <div class="learning-submission-mode-panel" hidden={!uploadOnly() && mode !== "upload"}>
        <form method="POST" class="learning-submission-upload" enctype="multipart/form-data">
          <input type="hidden" name="task_id" value={task.id} />
          <input type="hidden" name="task_kind" value={task.kind} />
          <input type="hidden" name="unit_type" value={unitType} />
          {#if moduleId}
            <input type="hidden" name="module_id" value={moduleId} />
          {/if}

          <label class="learning-submission-upload__dropzone">
            <span class="learning-submission-upload__title">Datei auswählen</span>
            <span class="learning-submission-upload__copy">
              {#if task.kind === "scratch"}
                `.sb3`-Datei hochladen
              {:else if task.kind === "calliope"}
                `.hex`-Datei hochladen
              {:else if task.kind === "filius"}
                `.fls`-Datei hochladen
              {:else}
                Bild oder PDF hochladen
              {/if}
            </span>
            <input aria-label="Datei auswählen" name="upload_file" type="file" />
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
      </div>

      {#if message === "feedback" && latestFeedbackSubmission()}
        <section class="learning-submission-history__section learning-submission-workspace__inline-feedback">
          <div class="learning-submission-workspace__feedback-header">
            <span class="learning-submission-history__intent learning-submission-history__intent--feedback">
              Rückmeldung
            </span>
            <span>{latestFeedbackSubmission()?.created_at}</span>
          </div>
          <p class="workspace-label">Neueste Rückmeldung</p>
          <div class="markdown-prose">
            {@html renderMarkdown(latestFeedbackSubmission()?.feedback_md ?? "")}
          </div>
        </section>
      {/if}
    </div>
  {:else}
    <section class="learning-submission-history">
      {#if historyLoading}
        <p class="learning-unit-empty-copy">Verlauf wird geladen …</p>
      {:else if historyError}
        <StatusMessage tone="error" title="Abgabeverlauf nicht verfügbar" description={historyError} />
      {:else if historyEntries.length}
        <div class="learning-submission-history__stack">
          {#each historyEntries as submission}
            <article class="learning-submission-history__entry">
              <header class="learning-submission-history__entry-header">
                <div>
                  <h6>Versuch {submission.attempt_nr}</h6>
                  <p>{submission.created_at}</p>
                </div>
                <div class="learning-submission-history__entry-meta">
                  <span class={`learning-submission-history__intent learning-submission-history__intent--${submission.intent}`}>
                    {humanIntent(submission)}
                  </span>
                  <span>{humanStatus(submission)}</span>
                </div>
              </header>

              {#if artifactEntry(submission)}
                <section class="learning-submission-history__section">
                  <p class="workspace-label">Abgabe</p>
                  <LearningSubmissionArtifactView submission={submission} />
                </section>
              {:else if submission.text_body}
                <section class="learning-submission-history__section">
                  <p class="workspace-label">Abgabe</p>
                  <div class="markdown-prose">
                    {@html renderMarkdown(submission.text_body)}
                  </div>
                </section>
              {/if}

              {#if fileEntry(submission) && !artifactEntry(submission)}
                <section class="learning-submission-history__section">
                  <p class="workspace-label">Datei</p>
                  {#if fileEntry(submission)?.mime.startsWith("image/")}
                    <img alt="Frühere Abgabe" class="learning-submission-history__image" src={fileEntry(submission)?.url} />
                  {:else if fileEntry(submission)?.mime === "application/pdf"}
                    <iframe class="learning-submission-history__frame" src={fileEntry(submission)?.url} title={`Abgabe Versuch ${submission.attempt_nr}`}></iframe>
                  {/if}
                  <p class="learning-submission-history__file-meta">
                    {fileEntry(submission)?.mime} · {formatBytes(fileEntry(submission)?.size)}
                  </p>
                  <a class="learning-work-item__link" href={fileEntry(submission)?.url}>Datei öffnen</a>
                </section>
              {/if}

              {#if submission.feedback_md}
                <section class="learning-submission-history__section">
                  <p class="workspace-label">Rückmeldung</p>
                  <div class="markdown-prose">
                    {@html renderMarkdown(submission.feedback_md)}
                  </div>
                </section>
              {/if}

              {#if submission.analysis_status === "failed"}
                <section class="learning-submission-history__section">
                  <p class="workspace-label">Analyse fehlgeschlagen</p>
                  <p>{learningSubmissionFailureMessage(submission)}</p>
                </section>
              {/if}

              {#if submission.analysis_json?.criteria_results?.length}
                <section class="learning-submission-history__section">
                  <p class="workspace-label">Auswertung</p>
                  <ul class="learning-unit-criteria">
                    {#each submission.analysis_json.criteria_results as criterion}
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
                </section>
              {/if}
            </article>
          {/each}
        </div>
      {:else}
        <p class="learning-unit-empty-copy">Noch keine Abgaben für diese Aufgabe.</p>
      {/if}
    </section>
  {/if}
</section>
