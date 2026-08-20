<script lang="ts">
  import { onMount } from "svelte";
  import LearnerMaterialContext from "$lib/components/learning-unit/LearnerMaterialContext.svelte";
  import LearnerTaskSplitDivider from "$lib/components/learning-unit/LearnerTaskSplitDivider.svelte";
  import StatusMessage from "$lib/components/ui/StatusMessage.svelte";
  import type { LearnerMaterialContextModule } from "$lib/learning-unit/workspace";
  import { renderMarkdown } from "$lib/utils/markdown";
  import type { LearningSubmission, LearningTask } from "$lib/types/learning";

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
  type HistoryState = "not_loaded" | "loading" | "loaded" | "failed" | "unavailable";

  let {
    learnerSub = null,
    courseId,
    task,
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
    onPause = null,
    showPauseAction = true,
    onCompleted = null
  }: {
    learnerSub?: string | null;
    courseId: string;
    task: LearningTask;
    existingSessionId?: string | null;
    readOnly?: boolean;
    compactSurface?: "task" | "materials";
    expandedModuleMaterialKeys?: Record<string, string[]>;
    expandedContextModuleIds?: string[];
    expandedSubmissionModuleIds?: string[];
    expandedSubmissionKeys?: string[];
    contextModules?: LearnerMaterialContextModule[];
    historyByTask?: Record<string, LearningSubmission[]>;
    historyStateByTask?: Record<string, HistoryState>;
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
        headers: { "content-type": "application/json", "idempotency-key": crypto.randomUUID() },
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
        headers: { "content-type": "application/json", "idempotency-key": crypto.randomUUID() },
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
      <aside class="dialog-sidebar" data-dialog-surface="materials" aria-label="Dialogpartner und Sitzungsaktionen">
          <header class="dialog-task-context">
            <p class="workspace-label">Aufgabe · KI-Dialog</p>
            <div class="dialog-task-context__instruction">{@html renderMarkdown(task.instruction_md)}</div>
          </header>
          <header class="dialog-context">
            <p class="workspace-label">KI-Dialogpartner</p>
            <h5>{session.dialog.partner_name}</h5>
            <div class="dialog-context__description markdown-prose">{@html renderMarkdown(session.dialog.partner_description_md)}</div>
          </header>

          <p class="dialog-context__meta" aria-label="Dialogstatus">
            <span>KI</span>
            <span>{session.dialog.response_mode === "hybrid" ? "Mit Satzanfängen" : "Freitext"}</span>
            <span>Runde {session.round_count}/{session.dialog.max_rounds}</span>
          </p>

          <div class="dialog-notice" role="note">
            <strong>Hinweis zur KI</strong>
            <span>Antworten können Fehler enthalten. Gib keine persönlichen oder vertraulichen Informationen ein.</span>
          </div>

        <LearnerMaterialContext
          {courseId}
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

        {#if session.status === "active" && !readOnly}
          <nav class="dialog-session-actions" aria-label="Sitzungsaktionen">
            {#if showPauseAction && onPause}
              <button class="workspace-top-action workspace-top-action--quiet" type="button" onclick={() => onPause?.()}>Pausieren</button>
            {:else if showPauseAction}
              <a class="workspace-top-action workspace-top-action--quiet" href={`/learning/courses/${encodeURIComponent(courseId)}`}>Pausieren</a>
            {/if}
            {#if !closingPhase && session.turns.length === 0}
              <button class="workspace-top-action workspace-top-action--quiet" type="button" disabled={pending} onclick={abandon}>Dialog ohne Abgabe abbrechen</button>
            {/if}
          </nav>
        {/if}
      </aside>

      <LearnerTaskSplitDivider
        value={taskColumnRatio}
        onPreview={(value) => onPreviewTaskColumnRatio?.(value)}
        onCommit={(value) => onCommitTaskColumnRatio?.(value)}
      />

      <div class="dialog-main" data-dialog-surface="task">
        <div class="dialog-transcript" role="log" aria-label="Dialogverlauf" aria-live="polite">
          <article class="dialog-message dialog-message--ai">
            <p class="dialog-message__speaker">KI · {session.dialog.partner_name}</p>
            <div class="markdown-prose">{@html renderMarkdown(session.dialog.opening_message_md)}</div>
          </article>
          {#each session.turns as turn}
            <article class="dialog-message dialog-message--student">
              <p class="dialog-message__speaker">Schüler · Du</p>
              <div class="markdown-prose">{@html renderMarkdown(turn.student_message_md)}</div>
              {#if turn.used_sentence_starter_md}<small class="dialog-message__help">Hilfestellung: Satzanfang verwendet</small>{/if}
            </article>
            {#if turn.assistant_reply_md}
              <article class="dialog-message dialog-message--ai">
                <p class="dialog-message__speaker">KI · {session.dialog.partner_name}</p>
                <div class="markdown-prose">{@html renderMarkdown(turn.assistant_reply_md)}</div>
              </article>
            {/if}
          {/each}
        </div>

        {#if session.status === "active" && !readOnly}
          {#if closingPhase}
            <section class="dialog-closing" aria-labelledby="dialog-closing-title">
              <header>
                <p class="workspace-label">Abschluss</p>
                <h6 id="dialog-closing-title">Abschluss vorbereiten</h6>
              </header>
              {#if session.dialog.closing_prompt_md}
                <label class="workspace-field"><span>{session.dialog.closing_prompt_md}</span><textarea bind:value={closingAnswer} maxlength="2000" rows="4"></textarea></label>
              {:else}
                <p class="workspace-note">Mit der Abgabe wird der Dialog endgültig abgeschlossen und ein Versuch verbraucht.</p>
              {/if}
              <div class="dialog-actions dialog-closing__actions">
                <button class="workspace-top-action workspace-top-action--quiet" type="button" disabled={pending} onclick={continueDialog}>Zurück zum Dialog</button>
                <button class="workspace-top-action workspace-top-action--accent" type="button" disabled={pending || Boolean(session.dialog.closing_prompt_md && !closingAnswer.trim())} onclick={complete}>Endgültig abgeben</button>
              </div>
            </section>
          {:else}
            <section class="dialog-composer" aria-label="Dialog fortsetzen">
              {#if session.dialog.response_mode === "hybrid" && session.initial_starters_status === "failed" && session.initial_generation_attempts < 3}
                <button class="workspace-top-action workspace-top-action--quiet" type="button" disabled={pending} onclick={start}>Erste Satzanfänge erneut erzeugen</button>
              {/if}
              {#if availableStarters().length}
                <div class="dialog-starters" aria-label="Satzanfang-Hilfen">
                  <p class="dialog-starters__label">Hilfestellung · Satzanfänge</p>
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
              {#if canSendAnswer() || canEndDialog() || latestFailedTurn() || hasTerminalDialogFailure()}
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
                    <button class="workspace-top-action workspace-top-action--quiet" type="button" disabled={pending} onclick={beginClosing}>Dialog beenden</button>
                  {/if}
                  {#if hasTerminalDialogFailure()}
                    <button class="workspace-top-action workspace-top-action--quiet" type="button" disabled={pending} onclick={abandon}>Dialog ohne Abgabe abbrechen</button>
                  {/if}
                </div>
              {/if}
            </section>
          {/if}
        {:else if session.status === "completed"}
          {@const submission = currentDialogSubmission()}
          {#if submission?.analysis_status === "completed" && submission.feedback_md}
            <section class="dialog-feedback" aria-label="Rückmeldung zum KI-Dialog">
              <header>
                <p class="workspace-label">Rückmeldung</p>
                <h6>Dein Dialog ist ausgewertet</h6>
              </header>
              <div class="markdown-prose">{@html renderMarkdown(submission.feedback_md)}</div>
            </section>
          {:else if submission?.analysis_status === "failed"}
            <div class="dialog-completed-note">
              <StatusMessage
                tone="error"
                title="Rückmeldung konnte nicht erstellt werden"
                description="Dein Dialog ist sicher gespeichert. Bitte versuche die Auswertung später erneut."
              />
            </div>
          {:else}
            <p class="workspace-note dialog-completed-note">Der Dialog wurde endgültig abgegeben. Die Rückmeldung wird erstellt.</p>
          {/if}
        {/if}
      </div>
    </div>
  {/if}
</section>
