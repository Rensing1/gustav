<script lang="ts">
  import { onMount } from "svelte";
  import LearningReferenceDocument from "$lib/components/learning-unit/LearningReferenceDocument.svelte";
  import { renderMarkdown } from "$lib/utils/markdown";
  import type { LearningMaterial, LearningSubmission, LearningTask } from "$lib/types/learning";

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
  type DialogContextEntry = {
    key: string;
    kind: "material" | "submission";
    label: string;
    title: string;
    material: LearningMaterial | null;
    submissions: LearningSubmission[];
    taskId?: string | null;
    current?: boolean;
    expanded?: boolean;
    removable?: boolean;
  };
  type DialogContextOption = {
    key: string;
    kind: "material" | "submission";
    id: string;
    moduleId: string | null;
    taskId: string | null;
    title: string;
    added: boolean;
  };
  type DialogContextModule = {
    id: string;
    title: string;
    current: boolean;
    loaded: boolean;
    loading: boolean;
    error: string | null;
    options: DialogContextOption[];
  };

  let {
    learnerSub = null,
    courseId,
    task,
    existingSessionId = null,
    readOnly = false,
    compactSurface = "task",
    contextMaterials = [],
    contextEntries = [],
    expandedReferenceKeys = [],
    contextPickerOpen = false,
    expandedContextModuleIds = [],
    contextModules = [],
    onSetCompactSurface = null,
    onOpenContext = null,
    onToggleCurrentMaterial = null,
    onToggleContextReference = null,
    onRemoveContextReference = null,
    onToggleContextPicker = null,
    onToggleContextModule = null,
    onAddContextReference = null,
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
    contextMaterials?: LearningMaterial[];
    contextEntries?: DialogContextEntry[];
    expandedReferenceKeys?: string[];
    contextPickerOpen?: boolean;
    expandedContextModuleIds?: string[];
    contextModules?: DialogContextModule[];
    onSetCompactSurface?: ((surface: "task" | "materials") => void) | null;
    onOpenContext?: ((key: string) => void | Promise<void>) | null;
    onToggleCurrentMaterial?: ((key: string) => void) | null;
    onToggleContextReference?: ((key: string) => void | Promise<void>) | null;
    onRemoveContextReference?: ((key: string) => void) | null;
    onToggleContextPicker?: (() => void) | null;
    onToggleContextModule?: ((moduleId: string) => void | Promise<void>) | null;
    onAddContextReference?: ((reference: {
      key: string;
      kind: "material" | "submission";
      id: string;
      moduleId: string | null;
      taskId: string | null;
    }) => void) | null;
    onPause?: (() => void | Promise<void>) | null;
    showPauseAction?: boolean;
    onCompleted?: (() => void | Promise<void>) | null;
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
    if (!session || session.round_count < 1 || session.turns.some((turn) => turn.status !== "completed")) return;
    closingPhase = true;
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

  async function request(path: string, options: RequestInit = {}): Promise<DialogSession> {
    const response = await fetch(`${baseUrl()}${path}`, { credentials: "include", cache: "no-store", ...options });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || "Der KI-Dialog ist gerade nicht verfügbar.");
    return (payload.session ?? payload) as DialogSession;
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
      const completed = await request(`/${session.id}/complete`, {
        method: "POST",
        headers: { "content-type": "application/json", "idempotency-key": crypto.randomUUID() },
        body: JSON.stringify({ closing_answer_md: closingAnswer || null })
      });
      clearClosingDraft(completed);
      acceptSession(completed);
      await onCompleted?.();
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
  {#if error}<p class="flash flash-error">{error}</p>{/if}
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
    <div class="dialog-layout" data-compact-surface={compactSurface} data-phase={closingPhase ? "closing" : "conversation"}>
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

        {#if contextEntries.length}
          <section class="dialog-context-materials" aria-labelledby="dialog-context-entries-title">
            <h6 id="dialog-context-entries-title">Aufgabe & Kontext</h6>
            {#each contextEntries as entry (entry.key)}
              <div class="learner-task-context__document-row">
                <LearningReferenceDocument
                  referenceKey={entry.key}
                  label={entry.label}
                  title={entry.title}
                  material={entry.material}
                  submissions={entry.submissions}
                  {courseId}
                  taskId={entry.taskId}
                  expanded={entry.expanded ?? expandedReferenceKeys.includes(entry.key)}
                  onToggle={entry.current ? onToggleCurrentMaterial : onToggleContextReference}
                  onOpenReader={onOpenContext}
                />
                {#if entry.removable}
                  <button
                    class="learner-task-context__remove"
                    type="button"
                    aria-label={`${entry.title} aus dem Kontext entfernen`}
                    onclick={() => onRemoveContextReference?.(entry.key)}
                  >Entfernen</button>
                {/if}
              </div>
            {/each}
          </section>
        {:else if contextMaterials.length}
          <section class="dialog-context-materials" aria-labelledby="dialog-context-materials-title">
            <h6 id="dialog-context-materials-title">Materialien</h6>
            {#each contextMaterials as material}
              <LearningReferenceDocument
                referenceKey={`material:${material.id}`}
                label="Material · Aktuelles Modul"
                title={material.title}
                {material}
                expanded={true}
                onToggle={onToggleContextReference}
                onOpenReader={onOpenContext}
              />
            {/each}
          </section>
        {/if}

        <button
          class="learner-task-context__add"
          type="button"
          aria-expanded={contextPickerOpen}
          onclick={() => onToggleContextPicker?.()}
        >+ Kontext hinzufügen</button>

        {#if contextPickerOpen}
          <section class="learner-context-picker" aria-label="Dialogkontext auswählen">
            {#each contextModules as contextModule}
              <div class="learner-context-picker__module">
                <button
                  class="learner-context-picker__module-toggle"
                  type="button"
                  aria-expanded={expandedContextModuleIds.includes(contextModule.id)}
                  onclick={() => onToggleContextModule?.(contextModule.id)}
                >
                  <span>{contextModule.current ? "Aktuelles Modul" : "Weiteres Modul"}</span>
                  <strong>{contextModule.title}</strong>
                </button>
                {#if expandedContextModuleIds.includes(contextModule.id)}
                  <div class="learner-context-picker__module-body">
                    {#if contextModule.loading}
                      <p class="workspace-note">Inhalte werden geladen …</p>
                    {:else if contextModule.error}
                      <p class="workspace-note workspace-note--error">{contextModule.error}</p>
                    {:else if contextModule.loaded}
                      {#each contextModule.options as option}
                        <button
                          class="learner-context-picker__add-item"
                          type="button"
                          disabled={option.added}
                          onclick={() => onAddContextReference?.({
                            key: option.key,
                            kind: option.kind,
                            id: option.id,
                            moduleId: option.moduleId,
                            taskId: option.taskId
                          })}
                        >
                          <span>{option.kind === "material" ? "Material" : "Eigene frühere Abgabe"}</span>
                          <strong>{option.title}</strong>
                        </button>
                      {/each}
                    {/if}
                  </div>
                {/if}
              </div>
            {/each}
          </section>
        {/if}

        {#if session.status === "active" && !readOnly}
          <nav class="dialog-session-actions" aria-label="Sitzungsaktionen">
            {#if showPauseAction && onPause}
              <button class="workspace-top-action workspace-top-action--quiet" type="button" onclick={() => onPause?.()}>Pausieren</button>
            {:else if showPauseAction}
              <a class="workspace-top-action workspace-top-action--quiet" href={`/learning/courses/${encodeURIComponent(courseId)}`}>Pausieren</a>
            {/if}
            {#if !closingPhase}
              {#if session.round_count > 0}
                <button class="workspace-top-action workspace-top-action--quiet" type="button" disabled={pending} onclick={beginClosing}>Dialog beenden</button>
              {:else}
                <button class="workspace-top-action workspace-top-action--quiet" type="button" disabled={pending} onclick={abandon}>Dialog ohne Abgabe abbrechen</button>
              {/if}
            {/if}
          </nav>
        {/if}
      </aside>

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
            {#if turn.status === "failed"}
              <button class="workspace-top-action workspace-top-action--quiet dialog-retry" type="button" disabled={pending || turn.generation_attempts >= 3} onclick={() => retry(turn)}>KI-Antwort erneut versuchen</button>
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
              {#if session.round_count < session.dialog.max_rounds && !session.turns.some((turn) => turn.status !== "completed") && (session.dialog.response_mode === "free_text" || session.initial_starters_status === "completed")}
                <label class="workspace-field"><span>Deine Antwort ({session.round_count}/{session.dialog.max_rounds})</span><textarea bind:value={message} maxlength="2000" rows="5"></textarea></label>
              {:else if session.round_count >= session.dialog.max_rounds}
                <p class="workspace-note">Maximale Rundenzahl erreicht.</p>
              {/if}
              {#if session.round_count < session.dialog.max_rounds && !session.turns.some((turn) => turn.status !== "completed") && (session.dialog.response_mode === "free_text" || session.initial_starters_status === "completed")}
                <div class="dialog-actions dialog-composer__actions">
                  <button class="workspace-top-action workspace-top-action--accent" type="button" disabled={pending || !message.trim()} onclick={send}>Antwort senden</button>
                </div>
              {/if}
            </section>
          {/if}
        {:else if session.status === "completed"}
          <p class="workspace-note dialog-completed-note">Der Dialog wurde endgültig abgegeben. Die Rückmeldung wird erstellt.</p>
        {/if}
      </div>
    </div>
  {/if}
</section>
