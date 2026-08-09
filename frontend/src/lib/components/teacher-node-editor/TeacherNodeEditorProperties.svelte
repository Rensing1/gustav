<script lang="ts">
  import type { TeacherUnitNodeEditorNode, TeacherUnitNodeEditorSettings } from "$lib/types/home";
  import StatusMessage from "$lib/components/ui/StatusMessage.svelte";

  let {
    node,
    settings,
    values = {},
    error = null
  }: {
    node: TeacherUnitNodeEditorNode;
    settings: TeacherUnitNodeEditorSettings;
    values?: { title?: string; required_prereq_count?: string };
    error?: string | null;
  } = $props();

  function titleValue(): string {
    return values.title ?? node.title;
  }

  function requiredPrereqCountValue(): string {
    if (values.required_prereq_count !== undefined) {
      return values.required_prereq_count;
    }
    return settings.kind === "module" ? String(settings.required_prereq_count) : "";
  }
</script>

<section class="workspace-panel teacher-node-editor-properties">
  <div class="teacher-node-editor-properties__head">
    <div>
      <p class="workspace-label">Eigenschaften</p>
      <h2>Knoten einstellen</h2>
    </div>
  </div>

  <form method="POST" action="?/saveNode" class="workspace-form teacher-node-editor-properties__form">
    <input type="hidden" name="kind" value={node.kind} />

    <label class="workspace-field">
      <span>Titel</span>
      <input name="title" type="text" value={titleValue()} maxlength="120" required />
    </label>

    {#if settings.kind === "module"}
      <label class="workspace-field">
        <span>Freischaltung</span>
        <input
          aria-describedby="teacher-node-editor-unlock-note"
          name="required_prereq_count"
          type="number"
          min="0"
          value={requiredPrereqCountValue()}
          required
        />
      </label>
      <p id="teacher-node-editor-unlock-note" class="workspace-note">
        Anzahl abgeschlossener Voraussetzungen, die vor diesem Modul erfüllt sein müssen.
      </p>
    {/if}

    {#if error}
      <StatusMessage tone="error" title="Änderungen nicht gespeichert" description={error} focusOnMount={true} />
    {/if}

    <div class="workspace-inline-actions">
      <button class="workspace-button" type="submit">Eigenschaften speichern</button>
    </div>
  </form>
</section>
