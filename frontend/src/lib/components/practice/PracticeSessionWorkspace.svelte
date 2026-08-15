<script lang="ts">
  import { invalidateAll } from "$app/navigation";
  import PracticeH5PTask from "$lib/components/PracticeH5PTask.svelte";
  import StatusMessage from "$lib/components/ui/StatusMessage.svelte";
  import { renderMarkdown } from "$lib/utils/markdown";
  import type { LearningPracticeAttempt, LearningPracticeSession } from "$lib/types/practice";
  import PracticeFeedback from "./PracticeFeedback.svelte";

  let {
    session,
    attempt,
    attemptKey,
    solution,
    nowIso
  }: {
    session: LearningPracticeSession;
    attempt: LearningPracticeAttempt | null;
    attemptKey: string;
    solution: string | null;
    nowIso: string;
  } = $props();

  let endDialog = $state<HTMLDialogElement | null>(null);
  const item = $derived(session.current_item);
  const visiblyHandledItems = $derived(
    session.completed_items + (item && item.status !== "active" ? 1 : 0)
  );
  const completedPercent = $derived(
    session.total_items > 0 ? Math.round(visiblyHandledItems / session.total_items * 100) : 0
  );

  function openEndDialog(): void {
    endDialog?.showModal();
  }
</script>

{#if item}
  <section class="practice-session" aria-labelledby="practice-session-title">
    <div class="practice-session__layout">
      <header class="practice-session__topline">
        <p class="practice-eyebrow">{item.module_title}</p>
        <h2 id="practice-session-title">Aufgabe {item.position} von {session.total_items}</h2>
      </header>

      <aside class="practice-session__rail" aria-label="Sitzungsfortschritt">
        <div>
          <p class="practice-eyebrow">Fortschritt</p>
          <p class="practice-session__count">{visiblyHandledItems} von {session.total_items} Aufgaben bearbeitet</p>
        </div>
        <div class="practice-progress">
          <progress max={session.total_items} value={visiblyHandledItems} aria-label={`${completedPercent} Prozent bearbeitet`}></progress>
          <span>{completedPercent} %</span>
        </div>
        <button class="practice-text-action" type="button" onclick={openEndDialog}>Sitzung beenden</button>
      </aside>

      <div class="practice-session__main">
        <article class="practice-task-card">
          <div class="practice-task-card__instruction markdown-prose">
            {@html renderMarkdown(item.instruction_md)}
          </div>

          {#if item.status === "active"}
            {#if item.kind === "native"}
              {#if attempt?.status === "failed"}
                <StatusMessage
                  tone="error"
                  title="Die Auswertung konnte nicht abgeschlossen werden"
                  description="Du kannst deine Antwort mit einer neuen Abgabe erneut prüfen lassen."
                  autoDismissMs={null}
                />
              {/if}
              <form method="POST" action="?/attempt" class="practice-answer-form">
                <input type="hidden" name="session_id" value={session.id} />
                <input type="hidden" name="item_id" value={item.id} />
                <input type="hidden" name="idempotency_key" value={attemptKey} />
                <label class="practice-answer-form__field">
                  <span>Deine Antwort</span>
                  <textarea name="answer_text" rows="8" placeholder="Formuliere deine Antwort …" required></textarea>
                </label>
                <div class="practice-task-card__actions">
                  <button
                    class="practice-button practice-button--secondary"
                    type="submit"
                    formaction="?/skip"
                    formnovalidate
                  >Aufgabe überspringen</button>
                  <button class="practice-button practice-button--primary" type="submit">Antwort prüfen</button>
                </div>
              </form>
            {:else if item.h5p_content_id}
              <PracticeH5PTask
                sessionId={session.id}
                itemId={item.id}
                courseId={item.course_id}
                taskId={item.task_id}
                contentId={item.h5p_content_id}
                onCompleted={invalidateAll}
              />
              <form method="POST" action="?/skip" class="practice-h5p-skip">
                <input type="hidden" name="session_id" value={session.id} />
                <input type="hidden" name="item_id" value={item.id} />
                <button class="practice-button practice-button--secondary" type="submit">Aufgabe überspringen</button>
              </form>
            {/if}
          {:else if item.status === "feedback" && attempt?.status === "completed"}
            <PracticeFeedback
              {attempt}
              sessionId={session.id}
              itemId={item.id}
              kind={item.kind}
              {solution}
              {nowIso}
            />
          {:else}
            <StatusMessage
              tone="progress"
              title="Deine Antwort wird ausgewertet"
              description="Die Rückmeldung erscheint automatisch, sobald sie fertig ist."
              autoDismissMs={null}
            />
          {/if}
        </article>
      </div>
    </div>
  </section>

  <dialog bind:this={endDialog} class="practice-end-dialog" aria-labelledby="practice-end-dialog-title">
    <form method="POST" action="?/end" class="practice-end-dialog__card">
      <input type="hidden" name="session_id" value={session.id} />
      <p class="practice-eyebrow">Sitzung beenden</p>
      <h2 id="practice-end-dialog-title">Möchtest du die Übung jetzt beenden?</h2>
      <p>Noch offene Aufgaben werden nur für diese Sitzung übersprungen. Deine bisherigen Antworten bleiben erhalten.</p>
      <div class="practice-end-dialog__actions">
        <button class="practice-button practice-button--secondary" type="button" onclick={() => endDialog?.close()}>Weiter üben</button>
        <button class="practice-button practice-button--danger" type="submit">Sitzung beenden</button>
      </div>
    </form>
  </dialog>
{/if}
