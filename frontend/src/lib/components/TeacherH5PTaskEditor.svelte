<script lang="ts">
  import { onMount } from "svelte";

  let {
    unitId,
    sectionId,
    taskId,
    contentId
  }: {
    unitId: string;
    sectionId: string;
    taskId: string;
    contentId?: string | null;
  } = $props();

  let root: HTMLDivElement | undefined;
  let status = $state("Lade H5P-Editor …");

  onMount(() => {
    if (!root) {
      status = "Der H5P-Editor konnte nicht initialisiert werden.";
      return;
    }

    let disposed = false;

    async function install(): Promise<void> {
      const entry = "/static/js/h5p_task_editor.js";
      await import(/* @vite-ignore */ entry);
      if (disposed || !root) {
        return;
      }
      document.body?.dispatchEvent(
        new CustomEvent("htmx:afterSwap", {
          detail: { target: root }
        })
      );
      status = "Bereit.";
    }

    void install().catch((error: unknown) => {
      status = error instanceof Error ? error.message : "H5P konnte nicht geladen werden.";
    });

    return () => {
      disposed = true;
    };
  });
</script>

<div
  bind:this={root}
  class="teacher-h5p-editor"
  data-h5p-task-editor="true"
  data-unit-id={unitId}
  data-section-id={sectionId}
  data-task-id={taskId}
  data-content-id={contentId ?? ""}
  data-task-patch-url={`/teaching/units/${unitId}/sections/${sectionId}/tasks/${taskId}/h5p`}
>
  <div class="teacher-h5p-editor__toolbar">
    <label>
      <span>Content-ID</span>
      <input class="workspace-input" id="h5pContentId" placeholder="(leer = neu)" size="22" />
    </label>
    <div class="teacher-h5p-editor__actions">
      <button class="workspace-button workspace-button--ghost" id="h5pNew" type="button">Neu</button>
      <button class="workspace-button workspace-button--ghost" id="h5pLoad" type="button">Laden</button>
      <button class="workspace-button" id="h5pSave" type="button">H5P speichern</button>
    </div>
  </div>
  <p class="teacher-h5p-editor__status" id="h5pStatus">{status}</p>
  <h5p-editor id="h5pEditor" content-id={contentId || "new"}></h5p-editor>
</div>
