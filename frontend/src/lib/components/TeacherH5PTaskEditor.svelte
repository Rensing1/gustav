<script lang="ts">
  import { onMount } from "svelte";
  import { loadH5PTaskEditorModule, type H5PTaskEditorMount } from "$lib/runtime/h5p-task-editor";

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
  const expiredSessionMessage = "Deine Sitzung ist abgelaufen. Bitte lade die Seite neu und melde dich bei Bedarf erneut an.";

  function toDisplayMessage(error: unknown): string {
    const raw = error instanceof Error ? error.message : String(error || "");
    if (raw === "unauthenticated") {
      return expiredSessionMessage;
    }
    return raw || "H5P konnte nicht geladen werden.";
  }

  onMount(() => {
    if (!root) {
      status = "Der H5P-Editor konnte nicht initialisiert werden.";
      return;
    }

    let disposed = false;
    let mountHandle: H5PTaskEditorMount | undefined;

    async function install(): Promise<void> {
      const module = await loadH5PTaskEditorModule();
      if (disposed || !root) {
        return;
      }
      mountHandle = module.mountH5PTaskEditor(root);
      await mountHandle.whenReady;
    }

    void install().catch((error: unknown) => {
      if (disposed) {
        return;
      }
      status = toDisplayMessage(error);
    });

    return () => {
      disposed = true;
      mountHandle?.destroy();
      mountHandle = undefined;
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
  data-task-h5p-base-url={`/api/teaching/units/${unitId}/sections/${sectionId}/tasks/${taskId}/h5p`}
>
  <div class="teacher-h5p-editor__toolbar">
    <div class="teacher-h5p-editor__identity">
      <p class="teacher-h5p-editor__eyebrow">Interaktive Aufgabe</p>
      <h4>H5P-Inhalt direkt in dieser Aufgabe pflegen</h4>
    </div>
    <div class="teacher-h5p-editor__actions">
      <input data-role="h5p-import-file" type="file" accept=".h5p,application/zip" hidden />
      <button class="workspace-button workspace-button--ghost" data-role="h5p-import" type="button">Importieren</button>
      <button class="workspace-button workspace-button--ghost" data-role="h5p-export" type="button">Export</button>
      <button class="workspace-button workspace-button--ghost" data-role="h5p-reset" type="button">Zurücksetzen</button>
      <button class="workspace-button" data-role="h5p-save" type="button">H5P speichern</button>
    </div>
  </div>
  <p class="teacher-h5p-editor__status" data-role="h5p-status">{status}</p>
  <div data-role="h5p-editor-host"></div>
</div>
