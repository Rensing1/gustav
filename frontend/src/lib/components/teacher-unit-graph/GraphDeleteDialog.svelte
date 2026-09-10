<script lang="ts">
  import { enhance } from "$app/forms";
  import { modalFocus } from "$lib/components/ui/modal-focus";
  import type { SubmitFunction } from "@sveltejs/kit";
  import StatusMessage from "$lib/components/ui/StatusMessage.svelte";

  import type { GraphDeletionImpact } from "$lib/teacher-unit-workspace/graph-deletion-impact";

  let {
    impact,
    action,
    error = null,
    onCancel,
    enhanceForm
  }: {
    impact: GraphDeletionImpact;
    action: string;
    error?: string | null;
    onCancel: () => void;
    enhanceForm?: SubmitFunction;
  } = $props();

  let pending = $state(false);

  const entityLabel = $derived(impact.kind === "phase" ? "Phase" : "Modul");
  const destructiveLabel = $derived(`${entityLabel} und Inhalte löschen`);

  const enhanceDeleteForm: SubmitFunction = (submission) => {
    pending = true;
    const delegated = enhanceForm?.(submission);
    return async (result) => {
      try {
        const callback = await delegated;
        if (callback) {
          await callback(result);
        } else {
          await result.update({ reset: false });
        }
      } finally {
        pending = false;
      }
    };
  };

  function cancel() {
    if (!pending) {
      onCancel();
    }
  }

</script>

<div class="dialog-backdrop graph-delete-dialog-backdrop">
  <button
    class="graph-delete-dialog-backdrop__dismiss"
    type="button"
    aria-label="Löschdialog schließen"
    onclick={cancel}
    disabled={pending}
  ></button>
  <div
    use:modalFocus={cancel}
    class="dialog-card graph-delete-dialog"
    role="dialog"
    aria-modal="true"
    aria-labelledby="graph-delete-dialog-title"
  >
    <div class="dialog-card__header">
      <div>
        <p class="workspace-label">Endgültig löschen</p>
        <h2 id="graph-delete-dialog-title">{entityLabel} löschen</h2>
      </div>
    </div>

    <p><strong>{impact.title}</strong> und die folgenden Inhalte werden unwiderruflich gelöscht:</p>
    <ul class="graph-delete-dialog__impact">
      {#if impact.kind === "phase"}<li>{impact.modulesCount} Module</li>{/if}
      <li>{impact.materialsCount} Materialien</li>
      <li>{impact.tasksCount} Aufgaben</li>
      <li>{impact.connectionsCount} Verbindungen</li>
    </ul>

    {#if error}
      <StatusMessage tone="error" title="Löschen nicht möglich" description={error} focusOnMount={true} />
    {/if}

    <form method="POST" {action} use:enhance={enhanceDeleteForm}>
      <input type="hidden" name={impact.kind === "phase" ? "phase_id" : "module_id"} value={impact.id} />
      <input type="hidden" name="confirmed" value="1" />
      <div class="dialog-card__actions graph-delete-dialog__actions">
        <button data-modal-initial class="workspace-link-action workspace-link-action--subtle" type="button" onclick={cancel} disabled={pending}>
          Abbrechen
        </button>
        <button class="workspace-link-action workspace-link-action--danger" type="submit" disabled={pending}>
          {pending ? "Wird gelöscht …" : destructiveLabel}
        </button>
      </div>
    </form>
  </div>
</div>
