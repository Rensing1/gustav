<script lang="ts">
  import type { ActionData, PageData } from "./$types";

  let { data, form }: { data: PageData; form: ActionData } = $props();

  function sectionId(): string {
    return data.editor.node.backing_section_id ?? data.editor.node.id;
  }
</script>

<svelte:head>
  <title>{data.editor.node.editor_title} | GUSTAV</title>
</svelte:head>

<section class="workspace-composer-header workspace-unit-header">
  <div class="workspace-composer-copy">
    <a class="workspace-back-link" href={`/teaching/units/${data.editor.unit.id}`}>Zurück zum Graph</a>
    <h1>{data.editor.node.editor_title}</h1>
    <p class="workspace-composer-copyline">
      {#if data.editor.node.kind === "module"}
        Modulinhalt bearbeiten
      {:else}
        Abschnittsinhalte bearbeiten
      {/if}
    </p>
  </div>
</section>

<div class="workspace-unit-content">
  <section class="workspace-panel workspace-unit-content-main">
    <div class="workspace-section-heading">
      <p class="workspace-label">Knoten</p>
      <h2>Inhalt</h2>
    </div>

    <form method="POST" action="?/saveNode" class="workspace-form">
      <input type="hidden" name="kind" value={data.editor.node.kind} />
      <label class="workspace-field">
        <span>Titel</span>
        <input name="title" type="text" value={data.editor.node.title} />
      </label>
      {#if data.editor.settings.kind === "module"}
        <label class="workspace-field">
          <span>Freischaltung</span>
          <input name="required_prereq_count" type="number" min="0" value={data.editor.settings.required_prereq_count} />
        </label>
      {/if}
      {#if form?.saveNode?.error}
        <p class="workspace-note workspace-note--error">{form.saveNode.error}</p>
      {/if}
      <button class="workspace-link-action" type="submit">Speichern</button>
    </form>

    <section class="workspace-unit-panel-list">
      <div class="workspace-section-heading">
        <p class="workspace-label">Material</p>
        <h2>Materialien</h2>
      </div>
      {#if data.editor.materials.length}
        <ul>
          {#each data.editor.materials as material}
            <li>
              <span>{material.title}</span>
              <form method="POST" action="?/deleteMaterial">
                <input type="hidden" name="section_id" value={sectionId()} />
                <input type="hidden" name="material_id" value={material.id} />
                <button class="workspace-link-action workspace-link-action--danger" type="submit">Entfernen</button>
              </form>
            </li>
          {/each}
        </ul>
      {:else}
        <p class="workspace-empty">Noch keine Materialien hinterlegt.</p>
      {/if}

      <form method="POST" action="?/createMaterial" class="workspace-form">
        <input type="hidden" name="section_id" value={sectionId()} />
        <label class="workspace-field">
          <span>Titel</span>
          <input name="title" type="text" />
        </label>
        <label class="workspace-field">
          <span>Inhalt</span>
          <textarea name="body_md" rows="5"></textarea>
        </label>
        {#if form?.createMaterial?.error}
          <p class="workspace-note workspace-note--error">{form.createMaterial.error}</p>
        {/if}
        <button class="workspace-link-action" type="submit">Material hinzufügen</button>
      </form>
    </section>

    <section class="workspace-unit-panel-list">
      <div class="workspace-section-heading">
        <p class="workspace-label">Aufgaben</p>
        <h2>Aufgaben</h2>
      </div>
      {#if data.editor.tasks.length}
        <ul>
          {#each data.editor.tasks as task}
            <li>
              <span>{task.instruction}</span>
              <form method="POST" action="?/deleteTask">
                <input type="hidden" name="section_id" value={sectionId()} />
                <input type="hidden" name="task_id" value={task.id} />
                <button class="workspace-link-action workspace-link-action--danger" type="submit">Entfernen</button>
              </form>
            </li>
          {/each}
        </ul>
      {:else}
        <p class="workspace-empty">Noch keine Aufgaben hinterlegt.</p>
      {/if}

      <form method="POST" action="?/createTask" class="workspace-form">
        <input type="hidden" name="section_id" value={sectionId()} />
        <label class="workspace-field">
          <span>Aufgabenstellung</span>
          <textarea name="instruction_md" rows="5"></textarea>
        </label>
        {#if form?.createTask?.error}
          <p class="workspace-note workspace-note--error">{form.createTask.error}</p>
        {/if}
        <button class="workspace-link-action" type="submit">Aufgabe hinzufügen</button>
      </form>
    </section>
  </section>

  <aside class="workspace-panel workspace-unit-context">
    <div class="workspace-sidecar-meta">
      <div>
        <span>Typ</span>
        <strong>{data.editor.node.kind === "module" ? "Modul" : "Abschnitt"}</strong>
      </div>
      {#if data.editor.settings.kind === "module"}
        <div>
          <span>Freischaltung</span>
          <strong>{data.editor.settings.required_prereq_count}</strong>
        </div>
      {/if}
    </div>
  </aside>
</div>
