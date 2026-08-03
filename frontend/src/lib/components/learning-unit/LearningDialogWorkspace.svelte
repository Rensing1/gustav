<script lang="ts">
  import { onMount } from "svelte";
  import { renderMarkdown } from "$lib/utils/markdown";
  import type { LearningTask } from "$lib/types/learning";

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

  let { learnerSub = null, courseId, task, existingSessionId = null, readOnly = false, onCompleted = null }: { learnerSub?: string | null; courseId: string; task: LearningTask; existingSessionId?: string | null; readOnly?: boolean; onCompleted?: (() => void | Promise<void>) | null } = $props();
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
  <div class="dialog-notice"><strong>KI-Dialog</strong> · Antworten können Fehler enthalten. Gib keine persönlichen oder vertraulichen Informationen ein.</div>
  {#if task.dialog}<div class="markdown-prose">{@html renderMarkdown(task.dialog.partner_description_md)}</div>{/if}
  {#if pending && !session}<p>Lädt …</p>{/if}
  {#if error}<p class="flash flash-error">{error}</p>{/if}
  {#if session}
    <div class="dialog-transcript">
      <article class="dialog-message dialog-message--ai"><strong>{session.dialog.partner_name}</strong><div class="markdown-prose">{@html renderMarkdown(session.dialog.opening_message_md)}</div></article>
      {#each session.turns as turn}
        <article class="dialog-message dialog-message--student"><strong>Du</strong><div class="markdown-prose">{@html renderMarkdown(turn.student_message_md)}</div>{#if turn.used_sentence_starter_md}<small>Mit Satzanfang-Hilfe</small>{/if}</article>
        {#if turn.assistant_reply_md}<article class="dialog-message dialog-message--ai"><strong>{session.dialog.partner_name}</strong><div class="markdown-prose">{@html renderMarkdown(turn.assistant_reply_md)}</div></article>{/if}
        {#if turn.status === "failed"}<button type="button" disabled={pending || turn.generation_attempts >= 3} onclick={() => retry(turn)}>KI-Antwort erneut versuchen</button>{/if}
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
          <div class="dialog-actions">
            <button class="workspace-top-action workspace-top-action--quiet" type="button" disabled={pending} onclick={continueDialog}>Zurück zum Dialog</button>
            <a class="workspace-top-action workspace-top-action--quiet" href={`/learning/courses/${encodeURIComponent(courseId)}`}>Pausieren</a>
            <button class="workspace-top-action workspace-top-action--accent" type="button" disabled={pending || Boolean(session.dialog.closing_prompt_md && !closingAnswer.trim())} onclick={complete}>Endgültig abgeben</button>
          </div>
        </section>
      {:else}
        <section class="dialog-composer" aria-label="Dialog fortsetzen">
          {#if session.dialog.response_mode === "hybrid" && session.initial_starters_status === "failed" && session.initial_generation_attempts < 3}
            <button class="workspace-top-action workspace-top-action--quiet" type="button" disabled={pending} onclick={start}>Erste Satzanfänge erneut erzeugen</button>
          {/if}
          {#if availableStarters().length}<div class="dialog-starters" aria-label="Satzanfänge">{#each availableStarters() as starter}<button type="button" onclick={() => chooseStarter(starter)}>{starter}</button>{/each}</div>{/if}
          {#if session.round_count < session.dialog.max_rounds && !session.turns.some((turn) => turn.status !== "completed") && (session.dialog.response_mode === "free_text" || session.initial_starters_status === "completed")}
            <label class="workspace-field"><span>Deine Antwort ({session.round_count}/{session.dialog.max_rounds})</span><textarea bind:value={message} maxlength="2000" rows="5"></textarea></label>
          {:else if session.round_count >= session.dialog.max_rounds}
            <p class="workspace-note">Maximale Rundenzahl erreicht.</p>
          {/if}
          <div class="dialog-actions">
            {#if session.round_count < session.dialog.max_rounds && !session.turns.some((turn) => turn.status !== "completed") && (session.dialog.response_mode === "free_text" || session.initial_starters_status === "completed")}
              <button class="workspace-top-action workspace-top-action--accent" type="button" disabled={pending || !message.trim()} onclick={send}>Antwort senden</button>
            {/if}
            {#if session.round_count > 0}
              <button class="workspace-top-action workspace-top-action--quiet" type="button" disabled={pending} onclick={beginClosing}>Dialog beenden</button>
            {:else}
              <button class="workspace-top-action workspace-top-action--quiet" type="button" disabled={pending} onclick={abandon}>Dialog ohne Abgabe abbrechen</button>
            {/if}
            <a class="workspace-top-action workspace-top-action--quiet" href={`/learning/courses/${encodeURIComponent(courseId)}`}>Pausieren</a>
          </div>
        </section>
      {/if}
    {:else if session.status === "completed"}<p class="workspace-note">Der Dialog wurde endgültig abgegeben. Die Rückmeldung wird erstellt.</p>{/if}
  {/if}
</section>

<style>
  .dialog-workspace,.dialog-transcript{display:grid;gap:1rem}.dialog-notice{padding:.8rem 1rem;border-radius:.75rem;background:#fff4d6;color:#563d00}.dialog-message{max-width:82%;padding:.8rem 1rem;border-radius:1rem;background:var(--color-surface-muted,#f1f4f8)}.dialog-message--student{justify-self:end;background:#e4efff}.dialog-starters{display:flex;flex-wrap:wrap;gap:.5rem}.dialog-starters button{border:1px solid #9bb2d1;border-radius:999px;background:white;padding:.45rem .75rem}
</style>
