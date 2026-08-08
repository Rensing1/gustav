<script lang="ts">
  import { enhance } from "$app/forms";
  import { onMount } from "svelte";
  import type { SubmitFunction } from "@sveltejs/kit";

  let {
    kind,
    id,
    title,
    sectionId,
    error = null,
    onCancel,
    enhanceForm
  }: {
    kind: "material" | "task";
    id: string;
    title: string;
    sectionId: string;
    error?: string | null;
    onCancel: () => void;
    enhanceForm?: SubmitFunction;
  } = $props();

  let dialogElement = $state<HTMLElement | null>(null);
  let cancelButton = $state<HTMLButtonElement | null>(null);
  let pending = $state(false);
  const entityLabel = $derived(kind === "material" ? "Material" : "Aufgabe");

  const enhanceDeleteForm: SubmitFunction = (submission) => {
    pending = true;
    const delegated = enhanceForm?.(submission);
    return async (result) => {
      try {
        const callback = await delegated;
        if (callback) await callback(result);
        else await result.update({ reset: false });
      } finally {
        pending = false;
      }
    };
  };

  function cancel() {
    if (!pending) onCancel();
  }

  function handleWindowKeydown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      event.preventDefault();
      cancel();
      return;
    }
    if (event.key !== "Tab" || !dialogElement) return;
    const focusable = Array.from(dialogElement.querySelectorAll<HTMLElement>('button:not([disabled])'));
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable.at(-1)!;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  onMount(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    cancelButton?.focus();
    return () => previousFocus?.focus();
  });
</script>

<svelte:window onkeydown={handleWindowKeydown} />

<div class="dialog-backdrop graph-delete-dialog-backdrop">
  <button class="graph-delete-dialog-backdrop__dismiss" type="button" aria-label="Löschdialog schließen" onclick={cancel} disabled={pending}></button>
  <div bind:this={dialogElement} class="dialog-card graph-delete-dialog" role="dialog" aria-modal="true" aria-labelledby="content-delete-dialog-title">
    <div class="dialog-card__header">
      <div>
        <p class="workspace-label">Endgültig löschen</p>
        <h2 id="content-delete-dialog-title">{entityLabel} löschen</h2>
      </div>
    </div>
    <p><strong>{title}</strong> wird unwiderruflich gelöscht.</p>
    {#if error}<p class="workspace-note workspace-note--error" role="alert">{error}</p>{/if}
    <form method="POST" action={kind === "material" ? "?/deleteMaterial" : "?/deleteTask"} use:enhance={enhanceDeleteForm}>
      <input type="hidden" name="section_id" value={sectionId} />
      <input type="hidden" name={kind === "material" ? "material_id" : "task_id"} value={id} />
      <input type="hidden" name="confirmed" value="1" />
      <div class="dialog-card__actions graph-delete-dialog__actions">
        <button bind:this={cancelButton} class="workspace-link-action workspace-link-action--subtle" type="button" onclick={cancel} disabled={pending}>Abbrechen</button>
        <button class="workspace-link-action workspace-link-action--danger" type="submit" disabled={pending}>{pending ? "Wird gelöscht …" : `${entityLabel} löschen`}</button>
      </div>
    </form>
  </div>
</div>
