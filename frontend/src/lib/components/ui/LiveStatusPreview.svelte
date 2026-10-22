<script lang="ts">
  import LiveTaskStrip from "../../../routes/live/LiveTaskStrip.svelte";
  import type { LiveStudentPanelTask } from "$lib/types/home";

  const states = [
    { label: "Offen", submitted: false, score: null },
    { label: "Unbewertet", submitted: true, score: null },
    { label: "0 Punkte", submitted: true, score: 0 },
    { label: "Über 0 bis unter 4", submitted: true, score: 2 },
    { label: "4 bis unter 8", submitted: true, score: 6 },
    { label: "Ab 8 Punkten", submitted: true, score: 10 }
  ];
  function task(state: typeof states[number], index: number): LiveStudentPanelTask {
    return { task_id: `preview-${index}`, task_position: 1, task_label: state.label,
      has_submission: state.submitted, average_score: state.score,
      is_latest_submission: false, href: "#live-status-preview" };
  }
</script>

<section id="live-status-preview" class="live-status-preview" aria-label="Live-Bewertungsfarben">
  <h1>Live-Bewertungsfarben</h1>
  <p>Produktive Aufgabenfelder · Beispieldaten ohne Speicherung</p>
  <div class="themes">
    {#each ["light", "dark"] as theme}
      <section data-theme={theme} class="theme-panel" aria-label={theme === "light" ? "Hellmodus" : "Dunkelmodus"}>
        <h2>{theme === "light" ? "Hellmodus" : "Dunkelmodus"}</h2>
        <div class="state-row column-labels"><span>Status</span><span>Normal</span><span>Ausgewählt</span></div>
        {#each states as state, index}
          {@const example = task(state, index)}
          <div class="state-row">
            <span>{state.label}</span>
            <LiveTaskStrip tasks={[example]} selectedTaskId={null} onOpen={(_, event) => event.preventDefault()} />
            <LiveTaskStrip tasks={[example]} selectedTaskId={example.task_id} onOpen={(_, event) => event.preventDefault()} />
          </div>
        {/each}
      </section>
    {/each}
  </div>
</section>

<style>
  .live-status-preview { margin: 24px auto 48px; max-width: 1100px; padding: 16px; scroll-margin-top: 80px; }
  h1 { font: 600 1.5rem/1.4 var(--font-ui); margin: 0; }
  p { color: var(--color-text-muted); margin: 8px 0 24px; }
  .themes { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
  .theme-panel { color: var(--color-text); background: var(--color-bg-surface); border: 1px solid var(--color-line); border-radius: 8px; padding: 24px; }
  h2 { font: 600 1.125rem var(--font-ui); margin: 0 0 20px; }
  .state-row { display: grid; grid-template-columns: minmax(0, 1fr) 60px 90px; align-items: center; gap: 8px; min-height: 66px; border-bottom: 1px solid var(--color-line); font: .875rem/1.4 var(--font-ui); }
  .state-row:last-child { border-bottom: 0; }
  .column-labels { min-height: 36px; color: var(--color-text-muted); font-size: .75rem; }
  /* The state is explicitly labelled in each row; keep the actual controls unmodified. */
  .state-row :global(.live-task-strip__caption) { display: none; }
  @media (max-width: 700px) {
    .themes { grid-template-columns: minmax(0, 1fr); }
    .theme-panel { padding: 16px; }
    .live-status-preview { padding: 0; }
  }
</style>
