<script lang="ts">
  import type { LearningUnitGraph, LearningUnitGraphModule } from "$lib/types/learning";
  let { graph, onOpen }: { graph: LearningUnitGraph; onOpen: (id: string) => void } = $props();
  const byId = $derived(new Map(graph.modules.map((module) => [module.id, module])));
  const phases = $derived([...graph.phases].sort((a, b) => a.position - b.position));

  function related(id: string, incoming: boolean): LearningUnitGraphModule[] {
    const ids = new Set(graph.edges.filter((edge) => incoming ? edge.to === id : edge.from === id)
      .map((edge) => incoming ? edge.from : edge.to));
    return [...ids].map((key) => byId.get(key)).filter((module): module is LearningUnitGraphModule => Boolean(module))
      .sort((a, b) => (graph.phases.find((phase) => phase.id === a.phase_id)?.position ?? 0)
        - (graph.phases.find((phase) => phase.id === b.phase_id)?.position ?? 0)
        || a.position_in_phase - b.position_in_phase);
  }

  // Only real dependencies affect order; independent branches retain the author's order.
  function orderedModules(phaseId: string): LearningUnitGraphModule[] {
    const remaining = graph.modules.filter((module) => module.phase_id === phaseId)
      .sort((a, b) => a.position_in_phase - b.position_in_phase);
    const result: LearningUnitGraphModule[] = [];
    while (remaining.length) {
      const index = remaining.findIndex((module) => !related(module.id, true)
        .some((parent) => remaining.some((candidate) => candidate.id === parent.id)));
      // A malformed cyclic graph must remain readable rather than hang the page.
      result.push(...remaining.splice(index < 0 ? 0 : index, 1));
    }
    return result;
  }

  function jump(event: MouseEvent, id: string) {
    event.preventDefault();
    const target = document.getElementById(`mobile-path-${id}`);
    target?.focus({ preventScroll: true });
    target?.scrollIntoView({ block: "center", behavior: "auto" });
  }
</script>

<nav class="mobile-learning-path" aria-label="Lernpfad nach Phasen">
  <p class="mobile-learning-path__intro">Offene Module kannst du frei wählen.</p>
  {#each phases as phase (phase.id)}
    {@const modules = orderedModules(phase.id)}
    {#if modules.length}
      <section class="mobile-learning-path__phase" aria-labelledby={`path-phase-${phase.id}`}>
        <h2 id={`path-phase-${phase.id}`}>{phase.title}</h2>
        {#each modules as module (module.id)}
          {@const parents = related(module.id, true)}
          {@const next = related(module.id, false)}
          <article id={`mobile-path-${module.id}`} class="mobile-learning-path__module" tabindex="-1">
            <header>
              <h3>{module.title}</h3>
              <span class="mobile-learning-path__status" data-status={module.status}>{module.status === "done" ? "Abgeschlossen" : module.status === "open" ? "Offen" : "Gesperrt"}</span>
            </header>
            {#if parents.length}
              <div class="mobile-learning-path__connections">
                <p>Voraussetzungen{module.prereq_required > 0 ? ` · ${module.prereq_done} von ${module.prereq_required} erfüllt` : ""}</p>
                {#if module.prereq_required > 0 && module.prereq_required < parents.length}
                  <small>{module.prereq_required} von {parents.length} Modulen nötig</small>
                {/if}
                <ul>
                  {#each parents as parent (parent.id)}
                    <li><span aria-hidden="true">↳</span> <a href={`#mobile-path-${parent.id}`} onclick={(event) => jump(event, parent.id)}>{parent.title}</a>{#if parent.status === "done"}<span aria-label="abgeschlossen"> ✓</span>{/if}</li>
                  {/each}
                </ul>
              </div>
            {/if}
            <p class="mobile-learning-path__progress">{module.module_kind === "practice" ? `${module.due_tasks_count} ${module.due_tasks_count === 1 ? "Wiederholung" : "Wiederholungen"} fällig` : `${module.tasks_done}/${module.tasks_total} Aufgaben erledigt · ${module.materials_count} ${module.materials_count === 1 ? "Material" : "Materialien"}`}</p>
            {#if module.status !== "locked"}
              <button class="workspace-top-action" type="button" onclick={() => onOpen(module.id)}>{module.module_kind === "practice" ? "Üben" : "Modul öffnen"}<span class="workspace-outline__sr-only">: {module.title}</span></button>
            {:else if !parents.length}
              <p class="workspace-note">Noch nicht freigeschaltet.</p>
            {/if}
            {#if next.length}
              <div class="mobile-learning-path__connections mobile-learning-path__connections--next">
                <p>Führt zu</p>
                <ul>{#each next as child (child.id)}<li><span aria-hidden="true">→</span> <a href={`#mobile-path-${child.id}`} onclick={(event) => jump(event, child.id)}>{child.title}</a></li>{/each}</ul>
              </div>
            {/if}
          </article>
        {/each}
      </section>
    {/if}
  {/each}
</nav>
