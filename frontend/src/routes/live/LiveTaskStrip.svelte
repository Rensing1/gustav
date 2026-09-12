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
  {#each tasks as task (task.task_id)}
    <a href={task.href}
      class={`live-task-strip__item live-task-strip__item--${tone(task)}`}
      class:is-active={selectedTaskId === task.task_id}
      class:is-latest={task.is_latest_submission}
      aria-current={selectedTaskId === task.task_id ? "true" : undefined}
      aria-label={label(task)} title={label(task)}
      onmouseenter={() => hoveredId = task.task_id}
      onmouseleave={() => hoveredId = null}
      onpointerdown={() => focusedId = null}
      onfocus={(event) => focusedId = event.currentTarget.matches(":focus-visible") ? task.task_id : null}
      onblur={() => focusedId = null}
      onclick={(event) => onOpen(task.task_id, event)}
    ></a>
  {/each}
</nav>
<p class="live-task-strip__caption workspace-note">{describedTask ? label(describedTask) : tasks.length ? "Wähle eine Aufgabe." : "Keine Aufgaben vorhanden."}</p>

<style>
  /* Preserve the original compact overview, including its state palette. */
  .live-task-strip {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(0.7rem, 0.9rem));
    gap: 0.28rem;
    justify-content: start;
  }
  .live-task-strip__item {
    width: 0.85rem;
    min-height: 1.15rem;
    border: 1px solid color-mix(in srgb, var(--color-border, #1b1b1b) 72%, transparent 28%);
    text-decoration: none;
    color: inherit;
    display: block;
    padding: 0;
    transition: transform 120ms ease, background 120ms ease, border-color 120ms ease;
  }
  .live-task-strip__item:hover,
  .live-task-strip__item:focus-visible {
    transform: translateY(-1px);
  }
  .live-task-strip__item--empty {
    background: color-mix(in srgb, var(--color-bg-muted, #f3f3f4) 92%, white 8%);
    border-color: color-mix(in srgb, var(--color-border, #1b1b1b) 20%, transparent 80%);
  }
  .live-task-strip__item--submitted-unscored {
    background: color-mix(in srgb, var(--color-border, #1b1b1b) 72%, white 28%);
    border-color: color-mix(in srgb, var(--color-border, #1b1b1b) 84%, transparent 16%);
  }
  .live-task-strip__item--score-zero { background: #7a0000; border-color: #7a0000; }
  .live-task-strip__item--score-low { background: #c62828; border-color: #c62828; }
  .live-task-strip__item--score-mid { background: #d87a00; border-color: #d87a00; }
  .live-task-strip__item--score-high { background: #2f8f5b; border-color: #2f8f5b; }
  .live-task-strip__item.is-active {
    outline: 2px solid var(--color-accent, #ff512f);
    outline-offset: -2px;
  }
  .live-task-strip__item.is-latest::after {
    content: "";
    display: block;
    width: 100%;
    height: 2px;
    background: var(--color-accent, #ff512f);
    margin-top: calc(1.15rem - 2px);
  }
  :global(.dark) .live-task-strip__item--empty {
    background: #4a4f54;
    border-color: color-mix(in srgb, white 26%, transparent 74%);
  }
  :global(.dark) .live-task-strip__item--submitted-unscored {
    background: #7b8288;
    border-color: #7b8288;
  }
  :global(.dark) .live-task-strip__item--score-zero { background: #ff4d4d; border-color: #ff4d4d; }
  :global(.dark) .live-task-strip__item--score-low { background: #ff6b57; border-color: #ff6b57; }
  :global(.dark) .live-task-strip__item--score-mid { background: #ff9a2f; border-color: #ff9a2f; }
  :global(.dark) .live-task-strip__item--score-high { background: #49b36f; border-color: #49b36f; }
  /* Reserve wrapped caption space so hover does not move a bottom-scrolled strip. */
  .live-task-strip__caption { margin: var(--space-2) 0 0; min-height: 2lh; overflow-wrap: anywhere; }
</style>
