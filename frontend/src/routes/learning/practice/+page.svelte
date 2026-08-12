<script lang="ts">
  import { browser } from "$app/environment";
  import { invalidateAll } from "$app/navigation";
  import PracticeH5PTask from "$lib/components/PracticeH5PTask.svelte";
  import type { PageData } from "./$types";

  let { data, form }: {
    data: PageData;
    form: { practice?: { error?: string; solution?: string } } | null;
  } = $props();

  $effect(() => {
    if (!browser || data.attempt?.status !== "pending") return;
    const timer = window.setTimeout(() => void invalidateAll(), 1500);
    return () => window.clearTimeout(timer);
  });

  const classificationLabel = (value: string | null) =>
    value === "secure" ? "Sicher beherrscht" : value === "partial" ? "Teilweise beherrscht" : "Noch nicht ausreichend";
</script>

<svelte:head><title>Üben | GUSTAV</title></svelte:head>

<div class="workspace-page learning-home">
  <h2>Üben</h2>

  {#if data.activeSession}
    <section class="workspace-panel">
      <p>{data.activeSession.completed_items} von {data.activeSession.total_items} Aufgaben abgeschlossen</p>
      {#if data.activeSession.current_item}
        <h3>{data.activeSession.current_item.instruction_md}</h3>
        {#if data.activeSession.current_item.criteria.length}
          <p>Kriterien: {data.activeSession.current_item.criteria.join(" · ")}</p>
        {/if}
        {#if data.activeSession.current_item.status === "active"}
          {#if data.activeSession.current_item.kind === "native"}
            {#if data.attempt?.status === "failed"}
              <p role="alert">Die Auswertung ist technisch fehlgeschlagen. Du kannst deine Antwort erneut senden.</p>
            {/if}
            <form method="POST" action="?/attempt">
              <input type="hidden" name="session_id" value={data.activeSession.id} />
              <input type="hidden" name="item_id" value={data.activeSession.current_item.id} />
              <input type="hidden" name="idempotency_key" value={data.attemptKey} />
              <label>
                <span>Deine Antwort</span>
                <textarea name="answer_text" rows="8" required></textarea>
              </label>
              <button type="submit">Antwort zur Auswertung senden</button>
            </form>
          {:else}
            {#if data.activeSession.current_item.h5p_content_id}
              <PracticeH5PTask
                sessionId={data.activeSession.id}
                itemId={data.activeSession.current_item.id}
                courseId={data.activeSession.current_item.course_id}
                taskId={data.activeSession.current_item.task_id}
                contentId={data.activeSession.current_item.h5p_content_id}
                onCompleted={invalidateAll}
              />
            {/if}
          {/if}
          <form method="POST" action="?/skip">
            <input type="hidden" name="session_id" value={data.activeSession.id} />
            <input type="hidden" name="item_id" value={data.activeSession.current_item.id} />
            <button type="submit">Aufgabe überspringen</button>
          </form>
        {:else if data.activeSession.current_item.status === "feedback"}
          {#if data.attempt?.status === "completed"}
            <section aria-live="polite">
              <h4>{classificationLabel(data.attempt.classification)}</h4>
              {#if data.attempt.feedback_md}<p>{data.attempt.feedback_md}</p>{/if}
              {#if data.attempt.due_at}<p>Nächste Fälligkeit: {new Date(data.attempt.due_at).toLocaleString("de-DE")}</p>{/if}
            </section>
          {/if}
          {#if data.activeSession.current_item.kind === "native"}
            {#if form?.practice?.solution}
              <section aria-live="polite">
                <h4>Musterlösung</h4>
                <p>{form.practice.solution}</p>
              </section>
            {:else}
              <form method="POST" action="?/solution">
                <input type="hidden" name="session_id" value={data.activeSession.id} />
                <input type="hidden" name="item_id" value={data.activeSession.current_item.id} />
                <button type="submit">Musterlösung anzeigen</button>
              </form>
            {/if}
          {/if}
          <form method="POST" action="?/continue">
            <input type="hidden" name="session_id" value={data.activeSession.id} />
            <button type="submit">Weiter</button>
          </form>
        {:else}
          <p aria-live="polite">Die Rückmeldung wird vorbereitet.</p>
        {/if}
      {/if}
      <form method="POST" action="?/end">
        <input type="hidden" name="session_id" value={data.activeSession.id} />
        <button type="submit">Sitzung beenden</button>
      </form>
    </section>
  {:else if data.stacks.length}
    <form method="POST" action="?/start" class="workspace-panel">
      <fieldset>
        <legend>Übungsstapel auswählen</legend>
        {#each data.stacks as stack}
          <label>
            <input
              type="checkbox"
              name="stack"
              value={`${stack.course_id}:${stack.practice_module_id}`}
              checked={data.selectedStack === `${stack.course_id}:${stack.practice_module_id}`}
            />
            <span>{stack.course_title} · {stack.unit_title} · {stack.module_title}</span>
            <small>{stack.due_tasks_count} fällig · {stack.task_count} insgesamt</small>
          </label>
        {/each}
      </fieldset>
      <label>
        <span>Modus</span>
        <select name="mode">
          <option value="due">Fällige Aufgaben</option>
          <option value="exam">Prüfungsvorbereitung</option>
        </select>
      </label>
      <button type="submit">Übung starten</button>
    </form>
  {:else}
    <section class="workspace-panel">
      <p class="workspace-empty">Aktuell sind keine offenen Übungsstapel verfügbar.</p>
    </section>
  {/if}

  {#if form?.practice?.error}
    <p role="alert">{form.practice.error}</p>
  {/if}
</div>
