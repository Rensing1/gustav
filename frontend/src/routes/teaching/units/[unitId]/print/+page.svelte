<script lang="ts">
  import PageActionHead from "$lib/components/ui/PageActionHead.svelte";
  import type { TeacherUnitPrintableItem, TeacherUnitPrintableNode } from "$lib/types/home";
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
  let selectedIds = $state<string[]>([]);
  let downloadBusy = $state(false);
  let downloadError = $state("");

  type SelectionGroup = {
    id: string;
    title: string;
    direct: boolean;
    nodes: TeacherUnitPrintableNode[];
  };

  function nodes(): TeacherUnitPrintableNode[] {
    if (data.printable.unit.unit_type === "linear") return data.printable.linear_sections;
    return data.printable.modular_phases.flatMap((phase) => phase.modules);
  }

  function items(node: TeacherUnitPrintableNode): TeacherUnitPrintableItem[] {
    return [...node.materials, ...node.tasks];
  }

  function allItems(): TeacherUnitPrintableItem[] {
    return nodes().flatMap(items);
  }

  function selectionGroups(): SelectionGroup[] {
    if (data.printable.unit.unit_type === "linear") {
      return data.printable.linear_sections.map((section) => ({
        id: section.id,
        title: section.title,
        direct: true,
        nodes: [section]
      }));
    }
    return data.printable.modular_phases.map((phase) => ({
      id: phase.id,
      title: phase.title,
      direct: false,
      nodes: phase.modules
    }));
  }

  function groupItems(group: SelectionGroup): TeacherUnitPrintableItem[] {
    return group.nodes.flatMap(items);
  }

  function isSelected(id: string): boolean {
    return selectedIds.includes(id);
  }

  function replaceSelection(ids: string[], checked: boolean) {
    const next = new Set(selectedIds);
    for (const id of ids) checked ? next.add(id) : next.delete(id);
    selectedIds = [...next];
  }

  function toggleItem(id: string, checked: boolean) {
    replaceSelection([id], checked);
  }

  function nodeAllSelected(node: TeacherUnitPrintableNode): boolean {
    const nodeItems = items(node);
    return nodeItems.length > 0 && nodeItems.every((item) => isSelected(item.id));
  }

  function nodeSomeSelected(node: TeacherUnitPrintableNode): boolean {
    return items(node).some((item) => isSelected(item.id));
  }

  function allSelected(): boolean {
    const available = allItems();
    return available.length > 0 && available.every((item) => isSelected(item.id));
  }

  function itemLabel(item: TeacherUnitPrintableItem): string {
    return item.content_type === "task" ? `Aufgabe: ${item.label}` : item.label;
  }

  function itemKind(item: TeacherUnitPrintableItem): string {
    if (item.content_type === "task") return "Aufgabe";
    if (item.mime_type === "application/pdf") return "PDF";
    if (item.mime_type?.startsWith("image/")) return "Bild";
    if (item.kind === "simulation") return "Simulation";
    return "Material";
  }

  function fileSize(bytes: number | null): string {
    if (!bytes) return "";
    return bytes < 1_048_576
      ? `${Math.ceil(bytes / 1024).toLocaleString("de-DE")} KB`
      : `${(bytes / 1_048_576).toLocaleString("de-DE", { maximumFractionDigits: 1 })} MB`;
  }

  function downloadFilename(response: Response): string {
    const match = response.headers.get("content-disposition")?.match(/filename="([a-zA-Z0-9._-]+)"/);
    return match?.[1] ?? "gustav-druckfassung.pdf";
  }

  async function downloadPdf(event: SubmitEvent) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!(form instanceof HTMLFormElement) || downloadBusy) return;
    downloadBusy = true;
    downloadError = "";
    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        credentials: "same-origin"
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({})) as { material?: { title?: string } };
        downloadError = payload.material?.title
          ? `„${payload.material.title}“ konnte nicht in die Druckfassung übernommen werden.`
          : "Die Druckfassung konnte nicht erstellt werden. Bitte prüfe deine Auswahl und versuche es erneut.";
        return;
      }
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = downloadFilename(response);
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch {
      downloadError = "Die Druckfassung konnte nicht erstellt werden. Bitte versuche es erneut.";
    } finally {
      downloadBusy = false;
    }
  }
</script>

<svelte:head>
  <title>Druckfassung · {data.printable.unit.title} | GUSTAV</title>
</svelte:head>

<div class="workspace-page printable-unit-page">
  <PageActionHead
    backHref={`/teaching/units/${data.printable.unit.id}`}
    backLabel="← Zur Lerneinheit"
    title="Druckfassung erstellen"
    copy="Wähle genau die Inhalte aus, die in der Schülerfassung erscheinen sollen."
  />

  <form
    class="printable-unit"
    method="POST"
    action={`/teaching/units/${data.printable.unit.id}/print/download`}
    aria-label="Inhalte für die Druckfassung auswählen"
    onsubmit={downloadPdf}
  >
    <div class="printable-unit__summary">
      <label class="printable-unit__select-all">
        <input
          type="checkbox"
          checked={allSelected()}
          indeterminate={selectedIds.length > 0 && !allSelected()}
          aria-label="Alle Inhalte auswählen"
          onchange={(event) => replaceSelection(allItems().map((item) => item.id), event.currentTarget.checked)}
        />
        <span>Alle Inhalte auswählen</span>
      </label>
      <strong>{selectedIds.length} von {allItems().length} Inhalten ausgewählt</strong>
    </div>

    {#if allItems().length === 0}
      <section class="printable-unit__empty">
        <h2>Noch keine druckbaren Inhalte</h2>
        <p>Füge der Lerneinheit zuerst Materialien oder Aufgaben hinzu.</p>
      </section>
    {:else}
      <div class="printable-unit__nodes">
        {#each selectionGroups() as group (group.id)}
          <fieldset class="printable-unit__group">
            <legend>
              <label>
                <input
                  type="checkbox"
                  checked={groupItems(group).length > 0 && groupItems(group).every((item) => isSelected(item.id))}
                  indeterminate={groupItems(group).some((item) => isSelected(item.id)) && !groupItems(group).every((item) => isSelected(item.id))}
                  aria-label={group.direct ? `${group.title} vollständig auswählen` : `Phase ${group.title} vollständig auswählen`}
                  onchange={(event) => replaceSelection(groupItems(group).map((item) => item.id), event.currentTarget.checked)}
                />
                <span>{group.direct ? group.title : `Phase: ${group.title}`}</span>
              </label>
            </legend>
            {#each group.nodes as node (node.id)}
              <section class:printable-unit__module={!group.direct}>
                {#if !group.direct}
                  <label class="printable-unit__module-select">
                    <input
                      type="checkbox"
                      checked={nodeAllSelected(node)}
                      indeterminate={nodeSomeSelected(node) && !nodeAllSelected(node)}
                      aria-label={`Modul ${node.title} vollständig auswählen`}
                      onchange={(event) => replaceSelection(items(node).map((item) => item.id), event.currentTarget.checked)}
                    />
                    <strong>{node.title}</strong>
                  </label>
                {/if}
                <div class="printable-unit__items">
                  {#each items(node) as item (item.id)}
                    <label class="printable-unit__item">
                      <input
                        type="checkbox"
                        name={item.content_type === "material" ? "material_id" : "task_id"}
                        value={item.id}
                        checked={isSelected(item.id)}
                        aria-label={itemLabel(item)}
                        onchange={(event) => toggleItem(item.id, event.currentTarget.checked)}
                      />
                      <span class="printable-unit__item-copy">
                        <strong>{item.label || (item.content_type === "task" ? "Aufgabe" : "Unbenanntes Material")}</strong>
                        <small>{itemKind(item)}{item.filename_original ? ` · ${item.filename_original}` : ""}{item.size_bytes ? ` · ${fileSize(item.size_bytes)}` : ""}</small>
                      </span>
                    </label>
                  {/each}
                </div>
              </section>
            {/each}
          </fieldset>
        {/each}
      </div>
    {/if}

    {#if downloadError}
      <div class="printable-unit__error" role="alert">{downloadError}</div>
    {/if}

    <div class="printable-unit__actions">
      <button
        class="workspace-link-action"
        type="submit"
        disabled={selectedIds.length === 0 || selectedIds.length > data.printable.limits.max_selected_items || downloadBusy}
      >{downloadBusy ? "PDF wird erstellt …" : "PDF herunterladen"}</button>
      <p>Maximal {data.printable.limits.max_selected_items} Inhalte, {data.printable.limits.max_pages} Seiten und 50 MB.</p>
    </div>
  </form>
</div>

<style>
  .printable-unit { display: grid; gap: 1rem; max-width: 64rem; }
  .printable-unit__summary, .printable-unit__actions { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 1rem 1.15rem; border: 1px solid var(--border-subtle); border-radius: 1rem; background: var(--surface-raised); }
  .printable-unit__select-all, legend label, .printable-unit__module-select, .printable-unit__item { display: flex; align-items: center; gap: .75rem; cursor: pointer; }
  .printable-unit__nodes { display: grid; gap: 1rem; }
  .printable-unit__group { min-width: 0; padding: .75rem 1rem 1rem; border: 1px solid var(--border-subtle); border-radius: 1rem; }
  .printable-unit__group legend { padding: 0 .35rem; font-size: 1.05rem; font-weight: 700; }
  .printable-unit__module { margin-top: .8rem; padding: .8rem; border-left: 2px solid var(--border-subtle); }
  .printable-unit__module-select { margin-bottom: .45rem; }
  .printable-unit__items { display: grid; gap: .35rem; margin-top: .5rem; }
  .printable-unit__item { padding: .7rem; border-radius: .7rem; }
  .printable-unit__item:hover { background: var(--surface-muted); }
  .printable-unit__item-copy { display: grid; gap: .15rem; }
  .printable-unit__item-copy small, .printable-unit__actions p { color: var(--text-muted); }
  .printable-unit__empty { padding: 1.5rem; border: 1px dashed var(--border-subtle); border-radius: 1rem; }
  .printable-unit__error { padding: .85rem 1rem; border: 1px solid var(--danger-border, #b42318); border-radius: .75rem; color: var(--danger-text, #8a1c13); }
  @media (max-width: 42rem) { .printable-unit__summary, .printable-unit__actions { align-items: stretch; flex-direction: column; } }
</style>
