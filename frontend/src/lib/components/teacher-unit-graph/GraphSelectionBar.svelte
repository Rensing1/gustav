<script lang="ts">
  import { formatGraphCount, formatGraphCounts } from "$lib/graph/teacher-unit-flow";

  export type GraphSelectionBarSelection =
    | {
        kind: "phase";
        title: string;
        moduleCount: number;
      }
    | {
        kind: "module";
        title: string;
        phaseTitle: string;
        materialsCount: number;
        tasksCount: number;
        editorHref: string;
      };

  let {
    selection,
    onOpenProperties,
    onAddModule,
    onFocusSelection,
    onRequestDelete
  }: {
    selection: GraphSelectionBarSelection;
    onOpenProperties: () => void;
    onAddModule?: (() => void) | null;
    onFocusSelection?: (() => void) | null;
    onRequestDelete: () => void;
  } = $props();
</script>

<section
  class="teacher-graph-selection-bar"
  aria-label={selection.kind === "module" ? "Ausgewähltes Modul" : "Ausgewählte Phase"}
>
  <div class="teacher-graph-selection-bar__copy">
    <span>{selection.kind === "module" ? `Modul · ${selection.phaseTitle}` : "Phase"}</span>
    <strong>{selection.title}</strong>
    <small>
      {selection.kind === "module"
        ? formatGraphCounts(selection.materialsCount, selection.tasksCount)
        : formatGraphCount(selection.moduleCount, "Modul", "Module")}
    </small>
  </div>

  <div class="teacher-graph-selection-bar__actions">
    {#if selection.kind === "module"}
      <a class="workspace-link-action" href={selection.editorHref}>Inhalt bearbeiten</a>
    {:else if onAddModule}
      <button class="workspace-link-action" type="button" onclick={onAddModule}>Modul hinzufügen</button>
    {/if}

    <button class="workspace-link-action workspace-link-action--subtle" type="button" onclick={onOpenProperties}>
      Eigenschaften
    </button>

    {#if onFocusSelection}
      <button class="workspace-link-action workspace-link-action--subtle" type="button" onclick={onFocusSelection}>
        Auswahl fokussieren
      </button>
    {/if}

    <details class="workspace-row-menu teacher-graph-selection-bar__menu">
      <summary aria-label="Weitere Aktionen">•••</summary>
      <div class="workspace-row-menu__panel">
        <button class="workspace-row-menu__danger" type="button" onclick={onRequestDelete}>
          {selection.kind === "module" ? "Modul löschen" : "Phase löschen"}
        </button>
      </div>
    </details>
  </div>
</section>
