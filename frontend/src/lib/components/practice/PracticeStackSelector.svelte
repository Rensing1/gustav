<script lang="ts">
  import type { LearningPracticeStack } from "$lib/types/practice";

  let {
    stacks,
    selectedStack,
    selectedMode
  }: {
    stacks: LearningPracticeStack[];
    selectedStack: string | null;
    selectedMode: "due" | "exam";
  } = $props();

  // The server-provided values intentionally initialize this form once. Later
  // interactions are local and must not be overwritten by page-data refreshes.
  // svelte-ignore state_referenced_locally
  let selectedKeys = $state<string[]>(selectedStack ? [selectedStack] : []);
  // svelte-ignore state_referenced_locally
  let mode = $state<"due" | "exam">(selectedMode);

  const keyFor = (stack: LearningPracticeStack) => `${stack.course_id}:${stack.practice_module_id}`;
  const isSelected = (stack: LearningPracticeStack) => selectedKeys.includes(keyFor(stack));
  const selectedStacks = $derived(stacks.filter(isSelected));
  const selectedTaskCount = $derived(
    selectedStacks.reduce(
      (sum, stack) => sum + (mode === "due" ? stack.due_tasks_count : stack.task_count),
      0
    )
  );
  const canStart = $derived(selectedKeys.length > 0 && selectedTaskCount > 0);
  const startLabel = $derived(
    selectedKeys.length === 0
      ? "Aufgaben auswählen"
      : `${selectedTaskCount} ${selectedTaskCount === 1 ? "Aufgabe" : "Aufgaben"} starten`
  );

  function toggleStack(stack: LearningPracticeStack): void {
    const key = keyFor(stack);
    selectedKeys = selectedKeys.includes(key)
      ? selectedKeys.filter((value) => value !== key)
      : [...selectedKeys, key];
  }
</script>

<section class="practice-selection" aria-labelledby="practice-selection-title">
  <header class="practice-intro">
    <p class="practice-eyebrow">Deine Wiederholungen</p>
    <h2 id="practice-selection-title">Was möchtest du üben?</h2>
    <p>Wähle ein oder mehrere Themen für deine nächste Übung.</p>
  </header>

  <form method="POST" action="?/start" class="practice-selection__form">
    <fieldset class="practice-fieldset">
      <legend>Themen auswählen</legend>
      <div class="practice-stack-list">
        {#each stacks as stack}
          <label class="practice-stack-card" data-selected={isSelected(stack)}>
            <input
              type="checkbox"
              name="stack"
              value={keyFor(stack)}
              checked={isSelected(stack)}
              onchange={() => toggleStack(stack)}
            />
            <span class="practice-stack-card__check" aria-hidden="true">
              <svg viewBox="0 0 24 24"><path d="m5 12 4 4L19 6" /></svg>
            </span>
            <span class="practice-stack-card__copy">
              <strong>{stack.module_title}</strong>
              <small>{stack.course_title} · {stack.unit_title}</small>
            </span>
            <span class="practice-stack-card__counts">
              <span>{stack.due_tasks_count} {stack.due_tasks_count === 1 ? "Aufgabe" : "Aufgaben"} fällig</span>
              <small>{stack.task_count} insgesamt</small>
            </span>
          </label>
        {/each}
      </div>
    </fieldset>

    <fieldset class="practice-fieldset practice-mode-picker">
      <legend>Übungsart</legend>
      <label class="practice-mode-option" data-selected={mode === "due"}>
        <input type="radio" name="mode" value="due" checked={mode === "due"} onchange={() => (mode = "due")} />
        <span class="practice-mode-option__marker" aria-hidden="true"></span>
        <span><strong>Fällige Wiederholungen</strong><small>Empfohlen · Aufgaben, die jetzt anstehen</small></span>
      </label>
      <label class="practice-mode-option" data-selected={mode === "exam"}>
        <input type="radio" name="mode" value="exam" checked={mode === "exam"} onchange={() => (mode = "exam")} />
        <span class="practice-mode-option__marker" aria-hidden="true"></span>
        <span><strong>Alle Aufgaben üben</strong><small>Zur gezielten Prüfungsvorbereitung</small></span>
      </label>
    </fieldset>

    {#if selectedKeys.length > 0 && mode === "due" && selectedTaskCount === 0}
      <p class="practice-selection__notice" role="status">Für diese Auswahl ist heute nichts fällig.</p>
    {/if}

    <footer class="practice-selection__footer">
      <p>{selectedKeys.length} {selectedKeys.length === 1 ? "Thema ausgewählt" : "Themen ausgewählt"}</p>
      <button class="practice-button practice-button--primary" type="submit" disabled={!canStart}>
        {startLabel}
        <span aria-hidden="true">→</span>
      </button>
    </footer>
  </form>
</section>
