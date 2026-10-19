<script lang="ts">
  import { browserUUID } from "$lib/utils/browser-uuid";
  import { onMount, tick } from "svelte";
  import LearnerTaskContext from "$lib/components/learning-unit/LearnerTaskContext.svelte";
  import LearningSubmissionPreview from "./LearningSubmissionPreview.svelte";
  import LearningDialogTranscriptDocument from "./LearningDialogTranscriptDocument.svelte";
  import DialogMessage from "$lib/components/learning-unit/DialogMessage.svelte";
  import LearnerTaskSplitDivider from "$lib/components/learning-unit/LearnerTaskSplitDivider.svelte";
  import StatusMessage from "$lib/components/ui/StatusMessage.svelte";
  import type { LearnerMaterialContextModule } from "$lib/learning-unit/workspace";
  import { renderMarkdown } from "$lib/utils/markdown";
  import type { LearningSubmission, LearningTask, SubmissionHistoryLoadState } from "$lib/types/learning";

  type DialogTurn = {
    id: string;
    round_nr: number;
    student_message_md: string;
    used_sentence_starter_md?: string | null;
    used_sentence_starter_source?: string | null;
    status: "generating" | "completed" | "failed";
    assistant_reply_md?: string | null;
    sentence_starters: string[];
    generation_attempts: number;
  };
  type DialogSession = {
    id: string;
    status: "active" | "completed" | "abandoned";
    round_count: number;
    dialog: NonNullable<LearningTask["dialog"]>;
    closing_answer_md?: string | null;
    initial_sentence_starters: string[];
    initial_starters_status: "not_required" | "pending" | "generating" | "completed" | "failed";
    initial_generation_attempts: number;
    turns: DialogTurn[];
  };
  type DialogSessionCompletionResult = {
    session: DialogSession;
    submission: LearningSubmission;
  };

  let {
    learnerSub = null,
    courseId,
    task,
    taskTitle = "Aufgabe",
    existingSessionId = null,
    readOnly = false,
    compactSurface = "task",
    expandedModuleMaterialKeys = {},
    expandedContextModuleIds = [],
    expandedSubmissionModuleIds = [],
    expandedSubmissionKeys = [],
    contextModules = [],
    historyByTask = {},
    historyStateByTask = {},
    focusedContextModuleId = null,
    closedContextModuleTitle = null,
    taskColumnRatio = null,
    onSetCompactSurface = null,
    onPreviewTaskColumnRatio = null,
    onCommitTaskColumnRatio = null,
    onOpenContext = null,
    onToggleContextMaterial = null,
    onToggleContextModule = null,
    onToggleSubmissionGroup = null,
    onToggleSubmission = null,
    onCloseContextModule = null,
    onUndoCloseContextModule = null,
    returnLabel = "Zurück zum Modul",
    onPause = null,
    showPauseAction = true,
    onCompleted = null
  }: {
    learnerSub?: string | null;
    courseId: string;
    task: LearningTask;
    taskTitle?: string;
    existingSessionId?: string | null;
    readOnly?: boolean;
    compactSurface?: "task" | "materials";
    expandedModuleMaterialKeys?: Record<string, string[]>;
    expandedContextModuleIds?: string[];
    expandedSubmissionModuleIds?: string[];
    expandedSubmissionKeys?: string[];
    contextModules?: LearnerMaterialContextModule[];
    historyByTask?: Record<string, LearningSubmission[]>;
    historyStateByTask?: Record<string, SubmissionHistoryLoadState>;
    focusedContextModuleId?: string | null;
    closedContextModuleTitle?: string | null;
    taskColumnRatio?: number | null;
    onSetCompactSurface?: ((surface: "task" | "materials") => void) | null;
    onPreviewTaskColumnRatio?: ((value: number) => void) | null;
    onCommitTaskColumnRatio?: ((value: number) => void) | null;
    onOpenContext?: ((key: string) => void | Promise<void>) | null;
    onToggleContextMaterial?: ((moduleId: string, key: string) => void) | null;
    onToggleContextModule?: ((moduleId: string) => void | Promise<void>) | null;
    onToggleSubmissionGroup?: ((moduleId: string) => void | Promise<void>) | null;
    onToggleSubmission?: ((key: string) => void) | null;
    onCloseContextModule?: ((moduleId: string) => void) | null;
    onUndoCloseContextModule?: (() => void) | null;
    returnLabel?: string;
    onPause?: (() => void | Promise<void>) | null;
    showPauseAction?: boolean;
    onCompleted?: ((submission: LearningSubmission) => void | Promise<void>) | null;
  } = $props();
  let session = $state<DialogSession | null>(null);
  let message = $state("");
  let closingAnswer = $state("");
  let closingPhase = $state(false);
  let restoredSessionId = $state<string | null>(null);
  let selectedStarter = $state<{ text: string; source: string } | null>(null);
  let pending = $state(false);
  let error = $state<string | null>(null);
  let transcriptElement = $state<HTMLDivElement | null>(null);
  let lastScrolledAssistantMessageId = $state<string | null>(null);

  function baseUrl(): string {
    return `/api/learning/courses/${encodeURIComponent(courseId)}/tasks/${encodeURIComponent(task.id)}/dialog-sessions`;
  }

  function closingDraftKey(sessionId: string): string | null {
    if (!learnerSub) return null;
    return `gustav.learning.dialog-closing-draft:${encodeURIComponent(learnerSub)}:${courseId}:${task.id}:${sessionId}`;
  }

  function clearClosingDraft(value: DialogSession) {
    const key = closingDraftKey(value.id);
    if (key) window.sessionStorage.removeItem(key);
  }

  function restoreClosingDraft(value: DialogSession) {
    if (restoredSessionId === value.id) return;
    restoredSessionId = value.id;
    if (value.status !== "active") {
      clearClosingDraft(value);
      closingPhase = false;
      closingAnswer = value.closing_answer_md ?? "";
      return;
    }
    const key = closingDraftKey(value.id);
    if (!key) return;
    try {
      const stored = JSON.parse(window.sessionStorage.getItem(key) ?? "null") as { phase?: unknown; closingAnswer?: unknown } | null;
      if (!stored) return;
      closingPhase = stored.phase === "closing" && value.round_count > 0;
      closingAnswer = typeof stored.closingAnswer === "string" ? stored.closingAnswer : "";
    } catch {
      window.sessionStorage.removeItem(key);
    }
  }

  function acceptSession(value: DialogSession) {
    session = value;
    restoreClosingDraft(value);
  }

  function beginClosing() {
    if (!canEndDialog()) return;
    closingPhase = true;
  }

  function conversationReady(): boolean {
    return Boolean(session && !session.turns.some((turn) => turn.status !== "completed"));
  }

  /**
   * Identifies the one AI message that the learner can answer now.
   * Failed, completed, read-only, and closing states deliberately have no
   * current question because they require a different next action.
   */
  function currentAssistantMessageId(): string | null {
    if (
      !session ||
      session.status !== "active" ||
      readOnly ||
      closingPhase ||
      session.round_count >= session.dialog.max_rounds ||
      !conversationReady()
    ) return null;

    for (let index = session.turns.length - 1; index >= 0; index -= 1) {
      const turn = session.turns[index];
      if (turn.assistant_reply_md) return turn.id;
    }
    return "opening";
  }

  function canSendAnswer(): boolean {
    return Boolean(
      session &&
      session.round_count < session.dialog.max_rounds &&
      conversationReady() &&
      (session.dialog.response_mode === "free_text" || session.initial_starters_status === "completed")
    );
  }

  function canEndDialog(): boolean {
    return Boolean(
      session &&
      session.round_count > 0 &&
      !session.turns.some((turn) => turn.status === "generating")
    );
  }

  function latestFailedTurn(): DialogTurn | null {
    const turn = session?.turns.at(-1) ?? null;
    return turn?.status === "failed" ? turn : null;
  }

  function retryLatestFailedTurn() {
    const turn = latestFailedTurn();
    if (turn && turn.generation_attempts < 3) void retry(turn);
  }

  function hasTerminalDialogFailure(): boolean {
    const turn = latestFailedTurn();
    return Boolean(turn && turn.generation_attempts >= 3);
  }

  function continueDialog() {
    closingPhase = false;
  }

  $effect(() => {
    const current = session;
    if (!current || current.status !== "active" || restoredSessionId !== current.id) return;
    const key = closingDraftKey(current.id);
    if (!key) return;
    if (!closingPhase && !closingAnswer) {
      window.sessionStorage.removeItem(key);
      return;
    }
    window.sessionStorage.setItem(
      key,
      JSON.stringify({ phase: closingPhase ? "closing" : "conversation", closingAnswer })
    );
  });

  $effect(() => {
    const messageId = currentAssistantMessageId();
    const transcript = transcriptElement;
    if (!messageId || !transcript || messageId === lastScrolledAssistantMessageId) return;
    lastScrolledAssistantMessageId = messageId;
    void tick().then(() => {
      if (transcriptElement) transcriptElement.scrollTop = transcriptElement.scrollHeight;
    });
  });

  $effect(() => {
    const transcript = transcriptElement;
    if (!transcript || typeof ResizeObserver === "undefined") return;

    // A responsive layout can shorten the transcript without changing its
    // messages. Keep the current question in view after that reflow.
    const observer = new ResizeObserver(() => {
      if (currentAssistantMessageId()) transcript.scrollTop = transcript.scrollHeight;
    });
    observer.observe(transcript);
    return () => observer.disconnect();
  });

  async function requestPayload<T>(path: string, options: RequestInit = {}): Promise<T> {
    const response = await fetch(`${baseUrl()}${path}`, { credentials: "include", cache: "no-store", ...options });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || "Der KI-Dialog ist gerade nicht verfügbar.");
    return payload as T;
  }

  async function request(path: string, options: RequestInit = {}): Promise<DialogSession> {
    const payload = await requestPayload<DialogSession | { session: DialogSession }>(path, options);
    return "session" in payload ? payload.session : payload;
  }

  async function start() {
    pending = true;
    error = null;
    try {
      acceptSession(await request("", { method: "POST", headers: { "content-type": "application/json" }, body: "{}" }));
    } catch (caught) {
      error = caught instanceof Error ? caught.message : "Der Dialog konnte nicht gestartet werden.";
    } finally {
      pending = false;
    }
  }

  function availableStarters(): string[] {
    const last = session?.turns.at(-1);
    return last?.sentence_starters?.length ? last.sentence_starters : session?.round_count === 0 ? session?.initial_sentence_starters ?? [] : [];
  }

  function currentDialogSubmission(): LearningSubmission | null {
    if (!session) return null;
    return historyByTask[task.id]?.find(
      (submission) => submission.kind === "dialog" && submission.dialog_session_id === session?.id
    ) ?? null;
  }

  function chooseStarter(text: string) {
    message = text;
    selectedStarter = { text, source: session?.round_count === 0 ? "initial" : `turn:${session?.turns.at(-1)?.id}` };
  }

  async function send() {
    if (!session || !message.trim()) return;
    pending = true;
    error = null;
    try {
      acceptSession(await request(`/${session.id}/turns`, {
        method: "POST",
        headers: { "content-type": "application/json", "idempotency-key": browserUUID() },
        body: JSON.stringify({ student_message_md: message, used_sentence_starter_md: selectedStarter?.text, used_sentence_starter_source: selectedStarter?.source })
      }));
      message = "";
      selectedStarter = null;
    } catch (caught) {
      error = caught instanceof Error ? caught.message : "Die Antwort konnte nicht gesendet werden.";
      if (session) await load();
    } finally {
      pending = false;
    }
  }

  async function load() {
    if (!session) return;
    try { acceptSession(await request(`/${session.id}`)); } catch { /* keep current safe state */ }
  }

  async function loadExisting(sessionId: string) {
    pending = true;
    try { acceptSession(await request(`/${sessionId}`)); }
    catch (caught) { error = caught instanceof Error ? caught.message : "Der Dialogverlauf konnte nicht geladen werden."; }
    finally { pending = false; }
  }

  async function retry(turn: DialogTurn) {
    if (!session) return;
    pending = true;
    error = null;
    try { acceptSession(await request(`/${session.id}/turns/${turn.id}/retry`, { method: "POST", headers: { "content-type": "application/json" }, body: "{}" })); }
    catch (caught) { error = caught instanceof Error ? caught.message : "Die Wiederholung ist fehlgeschlagen."; }
    finally { pending = false; }
  }

  async function complete() {
    if (!session) return;
    pending = true;
    error = null;
    try {
      const result = await requestPayload<DialogSessionCompletionResult>(`/${session.id}/complete`, {
        method: "POST",
        headers: { "content-type": "application/json", "idempotency-key": browserUUID() },
        body: JSON.stringify({ closing_answer_md: closingAnswer || null })
      });
      clearClosingDraft(result.session);
      acceptSession(result.session);
      await onCompleted?.(result.submission);
    } catch (caught) { error = caught instanceof Error ? caught.message : "Der Abschluss ist fehlgeschlagen."; }
    finally { pending = false; }
  }

  async function abandon() {
    if (!session) return;
    pending = true;
    try {
      const abandoned = await request(`/${session.id}/abandon`, { method: "POST", headers: { "content-type": "application/json" }, body: "{}" });
      clearClosingDraft(abandoned);
      acceptSession(abandoned);
      await onPause?.();
    }
    catch (caught) { error = caught instanceof Error ? caught.message : "Der Dialog konnte nicht abgebrochen werden."; }
    finally { pending = false; }
  }

  onMount(() => {
    if (existingSessionId) {
      void loadExisting(existingSessionId);
      return;
    }
    if (!readOnly) void start();
  });
</script>

<section class="dialog-workspace" aria-label="KI-Dialog">
  {#if pending && !session}<p>Lädt …</p>{/if}
  {#if error}<StatusMessage tone="error" title="Dialog konnte nicht fortgesetzt werden" description={error} />{/if}
  {#if session}
    <nav class="dialog-workspace__switch" aria-label="Arbeitsbereich wählen">
      <button
        class:dialog-workspace__switch-button--active={compactSurface === "task"}
        class="dialog-workspace__switch-button"
        type="button"
        aria-pressed={compactSurface === "task"}
        onclick={() => onSetCompactSurface?.("task")}
      >Aufgabe</button>
      <button
        class:dialog-workspace__switch-button--active={compactSurface === "materials"}
        class="dialog-workspace__switch-button"
        type="button"
        aria-pressed={compactSurface === "materials"}
        onclick={() => onSetCompactSurface?.("materials")}
      >Materialien</button>
    </nav>
    <div
      class="dialog-layout"
      data-compact-surface={compactSurface}
      data-phase={closingPhase ? "closing" : "conversation"}
      style={taskColumnRatio === null ? undefined : `--learner-task-column-ratio: ${taskColumnRatio}%`}
    >
      <LearnerTaskContext
        onOpenCurrentTask={() => onSetCompactSurface?.("task")}
        taskId={task.id}
        {courseId}
        {taskTitle}
        taskKind="KI-Dialog"
        instructionMd={task.instruction_md}
        roundCurrent={session.status === "completed" ? null : session.round_count}
        roundMaximum={session.status === "completed" ? null : session.dialog.max_rounds}
        variant="dialog"
        modules={contextModules}
        expandedModuleIds={expandedContextModuleIds}
        {expandedModuleMaterialKeys}
        {expandedSubmissionModuleIds}
        {expandedSubmissionKeys}
        {historyByTask}
        {historyStateByTask}
        focusedModuleId={focusedContextModuleId}
        closedModuleTitle={closedContextModuleTitle}
        onToggleModule={onToggleContextModule}
        onToggleMaterial={onToggleContextMaterial}
        onToggleSubmissionGroup={onToggleSubmissionGroup}
        onToggleSubmission={onToggleSubmission}
        onOpenReference={onOpenContext}
        onCloseModule={onCloseContextModule}
        onUndoCloseModule={onUndoCloseContextModule}
      />

      <LearnerTaskSplitDivider
        value={taskColumnRatio}
        onPreview={(value) => onPreviewTaskColumnRatio?.(value)}
        onCommit={(value) => onCommitTaskColumnRatio?.(value)}
      />

      <div class="dialog-main" class:dialog-main--result={session.status === "completed"} class:dialog-main--with-steps={session.status === "active" && !readOnly && Boolean(session.dialog.closing_prompt_md)} data-dialog-surface="task">
        {#if session.status === "active" && !readOnly && session.dialog.closing_prompt_md}
          <ol class="dialog-steps" aria-label="Ablauf der Aufgabe">
            <li aria-current={!closingPhase ? "step" : undefined}>Gespräch</li>
            <li aria-current={closingPhase ? "step" : undefined}>Abschlussaufgabe</li>
            <li>Abgabe</li>
          </ol>
        {/if}
        {#if session.status === "completed"}
          {@const submission = currentDialogSubmission()}
          <div class="dialog-result">
            {#if submission}
              <LearningSubmissionPreview {courseId} taskId={task.id} {taskTitle} hasSubmission
                state={{ status: "loaded", submission }} resultView />
            {:else}
              <h3>Abgegeben</h3>
              <LearningDialogTranscriptDocument {courseId} taskId={task.id} sessionId={session.id} compact />
              <p class="workspace-note" role="status">Die Rückmeldung wird geladen …</p>
            {/if}
            {#if onPause}
              <div class="dialog-result__actions">
                <button class="workspace-top-action workspace-top-action--accent" type="button" onclick={() => onPause?.()}>{returnLabel}</button>
              </div>
            {/if}
          </div>
        {:else}
        <div bind:this={transcriptElement} class="dialog-transcript" role="log" aria-label="Dialogverlauf" aria-live="polite">
          <DialogMessage kind="ai" speaker={session.dialog.partner_name} markdown={session.dialog.opening_message_md} current={currentAssistantMessageId() === "opening"} />
          {#each session.turns as turn}
            <DialogMessage kind="student" markdown={turn.student_message_md} usedStarter={Boolean(turn.used_sentence_starter_md)} />
            {#if turn.assistant_reply_md}
              <DialogMessage kind="ai" speaker={session.dialog.partner_name} markdown={turn.assistant_reply_md} current={currentAssistantMessageId() === turn.id} />
            {/if}
          {/each}
        </div>

        {#if session.status === "active" && !readOnly}
          {#if closingPhase}
            <section class="dialog-closing" aria-labelledby="dialog-closing-title">
              <header>
                <h3 id="dialog-closing-title">{session.dialog.closing_prompt_md ? "Zum Abschluss" : "Gespräch abgeben"}</h3>
              </header>
              {#if session.dialog.closing_prompt_md}
                <div class="dialog-closing__prompt markdown-prose" id="dialog-closing-prompt">{@html renderMarkdown(session.dialog.closing_prompt_md)}</div>
                <label class="workspace-field"><span>Deine Antwort</span><textarea aria-describedby="dialog-closing-prompt" bind:value={closingAnswer} maxlength="2000" rows="4"></textarea></label>
              {:else}
                <p class="workspace-note">Mit der Abgabe wird der Dialog endgültig abgeschlossen und ein Versuch verbraucht.</p>
              {/if}
              <div class="dialog-actions dialog-closing__actions">
                <button class="workspace-top-action workspace-top-action--quiet" type="button" disabled={pending} onclick={continueDialog}>Zurück zum Gespräch</button>
                {#if showPauseAction && onPause}
                  <button class="workspace-top-action workspace-top-action--quiet" type="button" onclick={() => onPause?.()}>Pausieren</button>
                {:else if showPauseAction}
                  <a class="workspace-top-action workspace-top-action--quiet" href={`/learning/courses/${encodeURIComponent(courseId)}`}>Pausieren</a>
                {/if}
                <button class="workspace-top-action workspace-top-action--accent" type="button" disabled={pending || Boolean(session.dialog.closing_prompt_md && !closingAnswer.trim())} onclick={complete}>{session.dialog.closing_prompt_md ? "Gespräch und Antwort abgeben" : "Gespräch abgeben"}</button>
              </div>
            </section>
          {:else}
            <section class="dialog-composer" aria-label="Dialog fortsetzen">
              {#if session.dialog.response_mode === "hybrid" && session.initial_starters_status === "failed" && session.initial_generation_attempts < 3}
                <button class="workspace-top-action workspace-top-action--quiet" type="button" disabled={pending} onclick={start}>Erste Satzanfänge erneut erzeugen</button>
              {/if}
              {#if availableStarters().length}
                <div class="dialog-starters" role="group" aria-label="Hilfestellungen">
                  <p class="dialog-starters__label">Hilfestellungen · Satzanfänge</p>
                  {#each availableStarters() as starter}
                    <button class="workspace-top-action workspace-top-action--quiet workspace-top-action--subtle dialog-starter" type="button" onclick={() => chooseStarter(starter)}>{starter}</button>
                  {/each}
                </div>
              {/if}
              {#if canSendAnswer()}
                <label class="workspace-field"><span>Deine Antwort ({session.round_count}/{session.dialog.max_rounds})</span><textarea bind:value={message} maxlength="2000" rows="5"></textarea></label>
              {:else if session.round_count >= session.dialog.max_rounds}
                <p class="workspace-note">Maximale Rundenzahl erreicht.</p>
              {/if}
              <div class="dialog-notice" role="note">
                <strong>Hinweis zur KI</strong>
                <span>Antworten können Fehler enthalten. Gib keine persönlichen oder vertraulichen Informationen ein.</span>
              </div>
              {#if canSendAnswer() || canEndDialog() || latestFailedTurn() || hasTerminalDialogFailure() || showPauseAction}
                <div class="dialog-actions dialog-composer__actions">
                  {#if latestFailedTurn() && (latestFailedTurn()?.generation_attempts ?? 3) < 3}
                    <button class="workspace-top-action workspace-top-action--quiet" type="button" disabled={pending} onclick={retryLatestFailedTurn}>KI-Antwort erneut versuchen</button>
                  {:else if latestFailedTurn()}
                    <p class="workspace-note dialog-retry-limit">Die KI-Antwort kann nicht erneut erzeugt werden.</p>
                  {/if}
                  {#if canSendAnswer()}
                    <button class="workspace-top-action workspace-top-action--accent" type="button" disabled={pending || !message.trim()} onclick={send}>Antwort senden</button>
                  {/if}
                  {#if canEndDialog()}
                    <button class="workspace-top-action workspace-top-action--quiet" type="button" disabled={pending} onclick={beginClosing}>{session.dialog.closing_prompt_md ? "Zur Abschlussaufgabe" : "Zur Abgabe"}</button>
                  {/if}
                  {#if session.turns.length === 0 || hasTerminalDialogFailure()}
                    <button class="workspace-top-action workspace-top-action--quiet" type="button" disabled={pending} onclick={abandon}>Dialog ohne Abgabe abbrechen</button>
                  {/if}
                  {#if showPauseAction && onPause}
                    <button class="workspace-top-action workspace-top-action--quiet" type="button" onclick={() => onPause?.()}>Pausieren</button>
                  {:else if showPauseAction}
                    <a class="workspace-top-action workspace-top-action--quiet" href={`/learning/courses/${encodeURIComponent(courseId)}`}>Pausieren</a>
                  {/if}
                </div>
              {/if}
            </section>
          {/if}
        {/if}
        {/if}
      </div>
    </div>
  {/if}
</section>
