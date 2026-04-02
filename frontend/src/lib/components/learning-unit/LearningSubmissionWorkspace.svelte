<script lang="ts">
  import { browser } from "$app/environment";
  import { onMount } from "svelte";

  import MarkdownWysiwygEditor from "$lib/components/learning-unit/MarkdownWysiwygEditor.svelte";
  import { renderMarkdown } from "$lib/utils/markdown";
  import type { LearningSubmission, LearningTask } from "$lib/types/learning";

  type WorkspaceTab = "submit" | "history";
  type SubmissionMode = "text" | "upload";

  let {
    courseId,
    task,
    taskTitle = "Aufgabe",
    unitType,
    moduleId = null,
    initialHistory = [],
    initialHistoryLoaded = false,
    initialTab = "submit",
    submitted = false,
    errorMessage = null,
    onClose = null
  }: {
    courseId: string;
    task: LearningTask;
    taskTitle?: string;
    unitType: "linear" | "modular";
    moduleId?: string | null;
    initialHistory?: LearningSubmission[];
    initialHistoryLoaded?: boolean;
    initialTab?: WorkspaceTab;
    submitted?: boolean;
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
    return task.kind === "visual" || task.kind === "scratch" || task.kind === "calliope";
  }

  function storageKey(): string {
    return `gustav.learning.submission-draft:${courseId}:${task.id}:${mode}`;
  }

  function restoreDraft() {
    if (!browser || uploadOnly() || mode !== "text") {
      return;
    }
    draftText = window.localStorage.getItem(storageKey()) ?? "";
  }

  async function loadHistory() {
    if (!browser || historyLoading || historyLoaded) {
      return;
    }
    historyLoading = true;
    historyError = null;
    try {
      const response = await fetch(
        `/api/learning/courses/${encodeURIComponent(courseId)}/tasks/${encodeURIComponent(task.id)}/submissions?limit=10&offset=0`,
        {
          credentials: "include",
          cache: "no-store"
        }
      );
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
    window.localStorage.setItem(storageKey(), value);
  }

  function humanStatus(submission: LearningSubmission): string {
    if (submission.kind === "h5p" && submission.score_raw !== null && submission.score_raw !== undefined) {
      return `${submission.analysis_status} · ${submission.score_raw}/${submission.score_max ?? 0}`;
    }
    return submission.analysis_status;
  }

  function fileEntry(submission: LearningSubmission): { mime: string; size: number; url: string } | null {
    return submission.files?.[0] ?? null;
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

  function taskSummary(): string {
    const plain = task.instruction_md
      .replace(/[#>*_`\-\[\]()]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    if (!plain) {
      return "Arbeite konzentriert an deiner Lösung.";
    }
    if (plain.length <= 180) {
      return plain;
    }
    return `${plain.slice(0, 177).trim()}…`;
  }

  onMount(() => {
    activeTab = initialTab;
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
      <p class="workspace-label">Abgabe</p>
      <h5>{taskTitle}</h5>
      <p class="learning-submission-workspace__meta">
        {#if uploadOnly()}
          Upload-Arbeitsbereich
        {:else}
          Schreib- und Abgabe-Arbeitsbereich
        {/if}
      </p>
      <p class="learning-submission-workspace__summary">{taskSummary()}</p>
    </div>

    <button class="workspace-top-action workspace-top-action--quiet" type="button" onclick={() => onClose?.()}>
      Zurück zum Inhalt
    </button>
  </header>

  <div class="learning-submission-workspace__tabs">
    <button
      class:workspace-tab--active={activeTab === "submit"}
      class="workspace-tab"
      type="button"
      onclick={() => setTab("submit")}
    >
      Abgabe
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
        <p class="flash flash-error">{errorMessage}</p>
      {/if}

      {#if !uploadOnly()}
        <div class="learning-submission-workspace__mode-switch">
          <button
            class:workspace-tab--active={mode === "text"}
            class="workspace-tab"
            type="button"
            onclick={() => setMode("text")}
          >
            Text
          </button>
          <button
            class:workspace-tab--active={mode === "upload"}
            class="workspace-tab"
            type="button"
            onclick={() => setMode("upload")}
          >
            Upload
          </button>
        </div>
      {/if}

      {#if mode === "text"}
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
            <button class="workspace-link-action" type="submit">Abgeben</button>
          </div>
        </form>
      {:else}
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
              {:else}
                Bild oder PDF hochladen
              {/if}
            </span>
            <input name="upload_file" type="file" />
          </label>

          <div class="learning-submission-editor__actions">
            <button class="workspace-link-action" type="submit">Abgeben</button>
          </div>
        </form>
      {/if}
    </div>
  {:else}
    <section class="learning-submission-history">
      {#if historyLoading}
        <p class="learning-unit-empty-copy">Verlauf wird geladen …</p>
      {:else if historyError}
        <p class="workspace-note workspace-note--error">{historyError}</p>
      {:else if historyEntries.length}
        <div class="learning-submission-history__stack">
          {#each historyEntries as submission}
            <article class="learning-submission-history__entry">
              <header class="learning-submission-history__entry-header">
                <div>
                  <h6>Versuch {submission.attempt_nr}</h6>
                  <p>{submission.created_at}</p>
                </div>
                <span>{humanStatus(submission)}</span>
              </header>

              {#if submission.text_body}
                <section class="learning-submission-history__section">
                  <p class="workspace-label">Abgabe</p>
                  <div class="markdown-prose">
                    {@html renderMarkdown(submission.text_body)}
                  </div>
                </section>
              {/if}

              {#if fileEntry(submission)}
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
