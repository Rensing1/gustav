<script lang="ts">
  import type { PageData } from "./$types";

  let { data, form }: { data: PageData; form: { practice?: { error?: string } } | null } = $props();
</script>

<svelte:head><title>Üben | GUSTAV</title></svelte:head>

<div class="workspace-page learning-home">
  <h2>Üben</h2>

  {#if !data.enabled}
    <section class="workspace-panel">
      <p class="workspace-empty">Übungssitzungen sind derzeit nicht freigeschaltet.</p>
    </section>
  {:else if data.activeSession}
    <section class="workspace-panel">
      <p>{data.activeSession.completed_items} von {data.activeSession.total_items} Aufgaben abgeschlossen</p>
      {#if data.activeSession.current_item}
        <h3>{data.activeSession.current_item.instruction_md}</h3>
        {#if data.activeSession.current_item.criteria.length}
          <p>Kriterien: {data.activeSession.current_item.criteria.join(" · ")}</p>
        {/if}
        {#if data.activeSession.current_item.status === "active"}
          <form method="POST" action="?/skip">
            <input type="hidden" name="session_id" value={data.activeSession.id} />
            <input type="hidden" name="item_id" value={data.activeSession.current_item.id} />
            <button type="submit">Aufgabe überspringen</button>
          </form>
        {:else if data.activeSession.current_item.status === "feedback"}
          <form method="POST" action="?/continue">
            <input type="hidden" name="session_id" value={data.activeSession.id} />
            <button type="submit">Weiter</button>
          </form>
        {:else}
          <p>Die Rückmeldung wird vorbereitet.</p>
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
