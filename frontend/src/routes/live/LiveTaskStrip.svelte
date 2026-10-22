<script lang="ts">
  import type { LiveStudentPanelTask } from "$lib/types/home";

  let { tasks, selectedTaskId, onOpen }: {
    tasks: LiveStudentPanelTask[];
    selectedTaskId: string | null;
    onOpen: (taskId: string, event: MouseEvent) => void;
  } = $props();
  let hoveredId = $state<string | null>(null);
  let focusedId = $state<string | null>(null);
  // Store identities rather than task snapshots so live refreshes also update
  // the caption. Keyboard exploration takes precedence over a resting mouse.
  const describedTask = $derived(
    tasks.find((task) => task.task_id === focusedId)
    ?? tasks.find((task) => task.task_id === hoveredId)
    ?? tasks.find((task) => task.task_id === selectedTaskId)
  );

  function label(task: LiveStudentPanelTask): string {
    const state = !task.has_submission ? "Noch offen"
      : typeof task.average_score === "number" ? `Ø ${task.average_score.toFixed(1)}` : "Noch unbewertet";
    return `${task.task_label}: ${state}`;
  }

  function tone(task: LiveStudentPanelTask): string {
    if (!task.has_submission) return "empty";
    const score = task.average_score;
    if (typeof score !== "number") return "submitted-unscored";
    if (score <= 0) return "score-zero";
    if (score >= 8) return "score-high";
    if (score >= 4) return "score-mid";
    return "score-low";
  }
</script>

<nav class="live-task-strip" aria-label="Aufgaben der Lerneinheit">
  {#each tasks as task, index (task.task_id)}
    <a href={task.href}
      class={`live-task-strip__item live-task-strip__item--${tone(task)}`}
      class:is-active={selectedTaskId === task.task_id}
      aria-current={selectedTaskId === task.task_id ? "true" : undefined}
      aria-label={label(task)} title={label(task)}
      onmouseenter={() => hoveredId = task.task_id}
      onmouseleave={() => hoveredId = null}
      onpointerdown={() => focusedId = null}
      onfocus={(event) => focusedId = event.currentTarget.matches(":focus-visible") ? task.task_id : null}
      onblur={() => focusedId = null}
      onclick={(event) => onOpen(task.task_id, event)}
    >{index + 1}</a>
  {/each}
</nav>
<p class="live-task-strip__caption workspace-note">{describedTask ? label(describedTask) : tasks.length ? "Wähle eine Aufgabe." : "Keine Aufgaben vorhanden."}</p>

<style>
  /* Numbered targets remain usable by touch; labels retain the full task context. */
  .live-task-strip {
    display: grid;
    grid-template-columns: repeat(auto-fill, 2.75rem);
    gap: 8px;
    justify-content: start;
  }
  .live-task-strip__item {
    width: 2.75rem;
    min-height: 2.75rem;
    border: 1px solid color-mix(in srgb, var(--color-border, #1b1b1b) 72%, transparent 28%);
    text-decoration: none;
    color: inherit;
    display: grid;
    place-items: center;
    position: relative;
    border-radius: 8px;
    font: 600 .875rem var(--font-ui);
    padding: 0;
    transition: transform 120ms ease, background 120ms ease, border-color 120ms ease;
  }
  .live-task-strip__item:hover,
  .live-task-strip__item:focus-visible {
    transform: translateY(-1px);
  }
  .live-task-strip__item--empty {
    background: transparent;
    border: 1px dashed var(--color-control-border);
  }
  .live-task-strip__item--submitted-unscored {
    background: var(--color-info-soft);
    color: var(--color-info);
    border-color: var(--color-info);
  }
  .live-task-strip__item--score-zero { background: var(--color-live-score-zero); border-color: var(--color-live-score-zero); color: var(--color-live-on-zero); }
  .live-task-strip__item--score-low { background: var(--color-live-score-low); border-color: var(--color-live-score-low); color: var(--color-live-on-low); }
  .live-task-strip__item--score-mid { background: var(--color-live-score-mid); border-color: var(--color-live-score-mid); color: var(--color-live-on-mid); }
  .live-task-strip__item--score-high { background: var(--color-live-score-high); border-color: var(--color-live-score-high); color: var(--color-live-on-high); }
  .live-task-strip__item.is-active {
    outline: 2px solid var(--color-accent, #ff512f);
    outline-offset: 2px;
  }
  /* Reserve wrapped caption space so hover does not move a bottom-scrolled strip. */
  .live-task-strip__caption { margin: var(--space-2) 0 0; min-height: 2lh; overflow-wrap: anywhere; }
</style>
