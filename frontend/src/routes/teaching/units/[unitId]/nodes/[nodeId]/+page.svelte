<script lang="ts">
  import { enhance } from "$app/forms";
  import { tick } from "svelte";

  import TeacherH5PTaskEditor from "$lib/components/TeacherH5PTaskEditor.svelte";
  import TeacherNodeEditorProperties from "$lib/components/teacher-node-editor/TeacherNodeEditorProperties.svelte";
  import TeacherNodeEditorSection from "$lib/components/teacher-node-editor/TeacherNodeEditorSection.svelte";
  import PageActionHead from "$lib/components/ui/PageActionHead.svelte";
  import type {
    TeacherUnitNodeEditorMaterial,
    TeacherUnitNodeEditorTask,
    TeacherUnitNodeEditorView
  } from "$lib/types/home";
  import type { ActionData, PageData } from "./$types";

  let { data, form }: { data: PageData; form: ActionData } = $props();

  type EditorActionSuccess = {
    ok: true;
    message: string;
    editor: TeacherUnitNodeEditorView;
    material_id?: string;
    task_id?: string;
  };

  type MaterialFormValues = {
    material_kind: string;
    title: string;
    body_md: string;
    alt_text: string;
  };

  type TaskFormValues = {
    task_kind: string;
    instruction_md: string;
    criteria_items: string[];
    teacher_context_md: string;
    due_at: string;
    max_attempts: string;
    h5p_content_id: string;
  };

  function plainEditor(editor: TeacherUnitNodeEditorView): TeacherUnitNodeEditorView {
    return JSON.parse(JSON.stringify(editor)) as TeacherUnitNodeEditorView;
  }

  function asSuccess(value: unknown): EditorActionSuccess | null {
    if (!value || typeof value !== "object") {
      return null;
    }
    const candidate = value as Partial<EditorActionSuccess>;
    return candidate.ok && candidate.editor ? (candidate as EditorActionSuccess) : null;
  }

  function actionValues<T extends Record<string, unknown>>(value: unknown): Partial<T> {
    if (!value || typeof value !== "object") {
      return {};
    }
    const candidate = value as { values?: Partial<T> };
    return candidate.values ?? {};
  }

  function sectionId(): string {
    return editorState.node.backing_section_id ?? editorState.node.id;
  }

  let editorState = $state<TeacherUnitNodeEditorView>(plainEditor(data.editor));
  let expandedMaterialId = $state<string | null>(null);
  let expandedTaskId = $state<string | null>(null);
  let showCreateMaterial = $state(false);
  let showCreateTask = $state(false);
  let createMaterialKind = $state<"markdown" | "file">("markdown");
  let createTaskKind = $state<"native" | "h5p" | "visual" | "scratch" | "calliope">("native");
  let handledForm = $state<ActionData | undefined>(undefined);
  let createMaterialCard = $state<HTMLElement | null>(null);
  let createTaskCard = $state<HTMLElement | null>(null);

  const enhanceEditorForm = () => {
    return async ({ update }: { update: (options?: { reset?: boolean; invalidateAll?: boolean }) => Promise<void> }) => {
      await update({ reset: false, invalidateAll: false });
    };
  };

  function materialValues(material: TeacherUnitNodeEditorMaterial): Partial<MaterialFormValues> {
    if (form?.saveMaterial?.material_id !== material.id) {
      return {};
    }
    return actionValues<MaterialFormValues>(form.saveMaterial);
  }

  function materialError(material: TeacherUnitNodeEditorMaterial): string | null {
    return form?.saveMaterial?.material_id === material.id ? (form.saveMaterial.error ?? null) : null;
  }

  function taskValues(task: TeacherUnitNodeEditorTask): Partial<TaskFormValues> {
    if (form?.saveTask?.task_id !== task.id) {
      return {};
    }
    return actionValues<TaskFormValues>(form.saveTask);
  }

  function taskError(task: TeacherUnitNodeEditorTask): string | null {
    return form?.saveTask?.task_id === task.id ? (form.saveTask.error ?? null) : null;
  }

  function createMaterialValues(): Partial<MaterialFormValues> {
    return actionValues<MaterialFormValues>(form?.createMaterial);
  }

  function createTaskValues(): Partial<TaskFormValues> {
    return actionValues<TaskFormValues>(form?.createTask);
  }

  function saveNodeValues(): { title?: string; required_prereq_count?: string } {
    return actionValues<{ title: string; required_prereq_count: string }>(form?.saveNode);
  }

  function saveNodeError(): string | null {
    return form?.saveNode?.error ?? null;
  }

  function materialKindLabel(material: TeacherUnitNodeEditorMaterial): string {
    return material.kind === "file" ? "Datei" : "Textmaterial";
  }

  function formatBytes(sizeBytes: number | null | undefined): string | null {
    if (!sizeBytes || sizeBytes < 1) {
      return null;
    }
    if (sizeBytes < 1024) {
      return `${sizeBytes} B`;
    }
    if (sizeBytes < 1024 * 1024) {
      return `${(sizeBytes / 1024).toFixed(1)} KB`;
    }
    return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function materialMeta(material: TeacherUnitNodeEditorMaterial): string {
    if (material.kind === "file") {
      const parts = [
        material.filename_original ?? "Datei",
        material.mime_type ?? null,
        formatBytes(material.size_bytes)
      ].filter(Boolean);
      return parts.join(" · ");
    }
    const content = material.body_md?.trim();
    return content ? "Markdown-Material" : "Textmaterial";
  }

  function taskKindLabel(task: TeacherUnitNodeEditorTask): string {
    switch (task.kind) {
      case "h5p":
        return "H5P";
      case "visual":
        return "Visuelle Aufgabe";
      case "scratch":
        return "Scratch";
      case "calliope":
        return "Calliope";
      default:
        return "Aufgabe";
    }
  }

  function taskTitle(task: TeacherUnitNodeEditorTask, index: number): string {
    const firstLine = task.instruction_md.trim().split("\n")[0]?.trim();
    return firstLine || `${taskKindLabel(task)} ${index + 1}`;
  }

  function taskMeta(task: TeacherUnitNodeEditorTask): string {
    const parts = [taskKindLabel(task)];
    if (task.criteria.length) {
      parts.push(`${task.criteria.length} Kriterien`);
    }
    if (task.max_attempts) {
      parts.push(`${task.max_attempts} Versuche`);
    }
    if (task.due_at) {
      parts.push("mit Fälligkeit");
    }
    return parts.join(" · ");
  }

  function dateTimeLocalValue(value: string | null | undefined): string {
    if (!value) {
      return "";
    }
    return value.slice(0, 16);
  }

  function fileHref(material: TeacherUnitNodeEditorMaterial, disposition: "inline" | "attachment"): string {
    return `/teaching/units/${editorState.unit.id}/sections/${sectionId()}/materials/${material.id}/file?disposition=${disposition}`;
  }

  function isPreviewableFile(material: TeacherUnitNodeEditorMaterial): boolean {
    if (material.kind !== "file") {
      return false;
    }
    return material.mime_type?.startsWith("image/") === true || material.mime_type === "application/pdf";
  }

  function isImageFile(material: TeacherUnitNodeEditorMaterial): boolean {
    return material.kind === "file" && material.mime_type?.startsWith("image/") === true;
  }

  function taskInstructionValue(task: TeacherUnitNodeEditorTask): string {
    return taskValues(task).instruction_md ?? task.instruction_md;
  }

  function taskCriteriaItems(task: TeacherUnitNodeEditorTask): string[] {
    return taskValues(task).criteria_items ?? task.criteria;
  }

  function createCriteriaItems(): string[] {
    return createTaskValues().criteria_items ?? [];
  }

  function criteriaSlots(values: string[]): string[] {
    return Array.from({ length: 10 }, (_, index) => values[index] ?? "");
  }

  function taskTeacherContextValue(task: TeacherUnitNodeEditorTask): string {
    return taskValues(task).teacher_context_md ?? task.teacher_context_md ?? "";
  }

  function taskDueAtValue(task: TeacherUnitNodeEditorTask): string {
    return taskValues(task).due_at ?? dateTimeLocalValue(task.due_at);
  }

  function taskMaxAttemptsValue(task: TeacherUnitNodeEditorTask): string {
    const formValue = taskValues(task).max_attempts;
    if (formValue !== undefined) {
      return formValue;
    }
    return task.max_attempts ? String(task.max_attempts) : "";
  }

  async function openCreateMaterial() {
    showCreateMaterial = !showCreateMaterial;
    expandedMaterialId = null;
    if (!showCreateMaterial) {
      return;
    }
    await tick();
    createMaterialCard?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  async function openCreateTask() {
    showCreateTask = !showCreateTask;
    expandedTaskId = null;
    if (!showCreateTask) {
      return;
    }
    await tick();
    createTaskCard?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function toggleMaterial(materialId: string) {
    expandedMaterialId = expandedMaterialId === materialId ? null : materialId;
    showCreateMaterial = false;
  }

  function toggleTask(taskId: string) {
    expandedTaskId = expandedTaskId === taskId ? null : taskId;
    showCreateTask = false;
  }

  $effect(() => {
    data.editor.node.id;
    editorState = plainEditor(data.editor);
    expandedMaterialId = null;
    expandedTaskId = null;
    showCreateMaterial = data.editor.materials.length === 0;
    showCreateTask = data.editor.tasks.length === 0;
    createMaterialKind = "markdown";
    createTaskKind = "native";
    handledForm = undefined;
  });

  $effect(() => {
    const materialKind = createMaterialValues().material_kind;
    if (materialKind === "file" || materialKind === "markdown") {
      createMaterialKind = materialKind;
    }
  });

  $effect(() => {
    const taskKind = createTaskValues().task_kind;
    if (taskKind === "h5p" || taskKind === "visual" || taskKind === "scratch" || taskKind === "calliope") {
      createTaskKind = taskKind;
      return;
    }
    if (taskKind === "native") {
      createTaskKind = "native";
    }
  });

  $effect(() => {
    if (!form || form === handledForm) {
      return;
    }

    handledForm = form;

    const saveMaterialSuccess = asSuccess(form.saveMaterial);
    const createMaterialSuccess = asSuccess(form.createMaterial);
    const deleteMaterialSuccess = asSuccess(form.deleteMaterial);
    const reorderMaterialSuccess = asSuccess(form.reorderMaterial);
    const saveTaskSuccess = asSuccess(form.saveTask);
    const createTaskSuccess = asSuccess(form.createTask);
    const deleteTaskSuccess = asSuccess(form.deleteTask);
    const reorderTaskSuccess = asSuccess(form.reorderTask);

    const success =
      saveMaterialSuccess
      ?? createMaterialSuccess
      ?? deleteMaterialSuccess
      ?? reorderMaterialSuccess
      ?? saveTaskSuccess
      ?? createTaskSuccess
      ?? deleteTaskSuccess
      ?? reorderTaskSuccess;

    if (success) {
      editorState = plainEditor(success.editor);
      if (saveMaterialSuccess || reorderMaterialSuccess) {
        expandedMaterialId = success.material_id ?? expandedMaterialId;
      } else if (createMaterialSuccess) {
        expandedMaterialId = success.material_id ?? success.editor.materials.at(-1)?.id ?? null;
        showCreateMaterial = false;
      } else if (deleteMaterialSuccess) {
        expandedMaterialId = null;
      }

      if (saveTaskSuccess || reorderTaskSuccess) {
        expandedTaskId = success.task_id ?? expandedTaskId;
      } else if (createTaskSuccess) {
        expandedTaskId = success.task_id ?? success.editor.tasks.at(-1)?.id ?? null;
        showCreateTask = false;
      } else if (deleteTaskSuccess) {
        expandedTaskId = null;
      }
      return;
    }

    if (form.saveMaterial?.material_id) {
      expandedMaterialId = form.saveMaterial.material_id;
    }
    if (form.saveTask?.task_id) {
      expandedTaskId = form.saveTask.task_id;
    }
    if (form.createMaterial?.error) {
      showCreateMaterial = true;
    }
    if (form.createTask?.error) {
      showCreateTask = true;
    }
  });
</script>

<svelte:head>
  <title>{editorState.node.editor_title} | GUSTAV</title>
</svelte:head>

<div class="workspace-page teacher-node-editor-page">
  <PageActionHead
    backHref={`/teaching/units/${editorState.unit.id}`}
    backLabel="Zurück zum Graph"
    title={editorState.node.editor_title}
  />

  <section class="workspace-node-editor workspace-node-editor--content-only">
    <TeacherNodeEditorProperties
      node={editorState.node}
      settings={editorState.settings}
      values={saveNodeValues()}
      error={saveNodeError()}
    />

    <TeacherNodeEditorSection
      eyebrow="Material"
      title="Materialien"
      createLabel="Material hinzufügen"
      showCreate={showCreateMaterial}
      hasItems={editorState.materials.length > 0}
      emptyMessage="Noch keine Materialien hinterlegt."
      onCreate={openCreateMaterial}
    >
      {#snippet create()}
        <form method="POST" action="?/createMaterial" class="workspace-node-editor-card-form" use:enhance={enhanceEditorForm}>
          <input type="hidden" name="section_id" value={sectionId()} />

          <label class="workspace-field">
            <span>Materialtyp</span>
            <select bind:value={createMaterialKind} name="material_kind">
              <option value="markdown">Textmaterial</option>
              <option value="file">Datei</option>
            </select>
          </label>

          <label class="workspace-field">
            <span>Titel</span>
            <input name="title" type="text" value={createMaterialValues().title ?? ""} />
          </label>

          {#if createMaterialKind === "file"}
            <label class="workspace-field">
              <span>Datei</span>
              <input name="upload_file" type="file" />
            </label>
            <label class="workspace-field">
              <span>Alternativtext</span>
              <input name="alt_text" type="text" value={createMaterialValues().alt_text ?? ""} />
            </label>
          {:else}
            <label class="workspace-field">
              <span>Inhalt</span>
              <textarea name="body_md" rows="7">{createMaterialValues().body_md ?? ""}</textarea>
            </label>
          {/if}

          {#if form?.createMaterial?.error}
            <p class="workspace-note workspace-note--error">{form.createMaterial.error}</p>
          {/if}

          <div class="workspace-node-editor-card-actions">
            <button class="workspace-link-action" type="submit">Material hinzufügen</button>
          </div>
        </form>
      {/snippet}

      {#snippet list()}
        {#each editorState.materials as material}
          <article class:workspace-node-editor-card--expanded={expandedMaterialId === material.id} class="workspace-node-editor-card workspace-node-editor-entry">
            <button class="workspace-node-editor-entry-summary" type="button" onclick={() => toggleMaterial(material.id)}>
              <div class="workspace-node-editor-entry-summary-bar"></div>
              <div class="workspace-node-editor-entry-summary-copy">
                <p class="workspace-node-editor-entry-kicker">{materialKindLabel(material)}</p>
                <h3>{material.title}</h3>
                <p class="workspace-node-editor-entry-meta">{materialMeta(material)}</p>
              </div>
              <span aria-hidden="true" class="workspace-node-editor-entry-toggle">{expandedMaterialId === material.id ? "−" : "+"}</span>
            </button>

            {#if expandedMaterialId === material.id}
              <div class="workspace-node-editor-entry-body">
                <div class="workspace-node-editor-entry-toolbar">
                  <span class="workspace-node-editor-entry-toolbar-spacer"></span>
                  <details class="workspace-node-editor-card-menu">
                    <summary class="workspace-node-editor-card-menu__toggle">Aktionen</summary>
                    <div class="workspace-node-editor-card-menu__panel">
                      <form method="POST" action="?/reorderMaterial" use:enhance={enhanceEditorForm}>
                        <input type="hidden" name="material_id" value={material.id} />
                        <input type="hidden" name="direction" value="up" />
                        <button type="submit">Nach oben</button>
                      </form>
                      <form method="POST" action="?/reorderMaterial" use:enhance={enhanceEditorForm}>
                        <input type="hidden" name="material_id" value={material.id} />
                        <input type="hidden" name="direction" value="down" />
                        <button type="submit">Nach unten</button>
                      </form>
                      <form method="POST" action="?/deleteMaterial" use:enhance={enhanceEditorForm}>
                        <input type="hidden" name="section_id" value={sectionId()} />
                        <input type="hidden" name="material_id" value={material.id} />
                        <button class="workspace-node-editor-card-menu__danger" type="submit">Entfernen</button>
                      </form>
                    </div>
                  </details>
                </div>

                {#if material.kind === "file" && isPreviewableFile(material)}
                  <div class="workspace-node-editor-file-preview">
                    {#if isImageFile(material)}
                      <img alt={material.alt_text ?? material.title} src={fileHref(material, "inline")} />
                    {:else}
                      <iframe src={fileHref(material, "inline")} title={`Vorschau ${material.title}`}></iframe>
                    {/if}
                  </div>
                {/if}

                <form method="POST" action="?/saveMaterial" class="workspace-node-editor-card-form" use:enhance={enhanceEditorForm}>
                  <input type="hidden" name="section_id" value={sectionId()} />
                  <input type="hidden" name="material_id" value={material.id} />
                  <input type="hidden" name="kind" value={material.kind} />

                  <label class="workspace-field">
                    <span>Titel</span>
                    <input name="title" type="text" value={materialValues(material).title ?? material.title} />
                  </label>

                  {#if material.kind === "markdown"}
                    <label class="workspace-field">
                      <span>Inhalt</span>
                      <textarea name="body_md" rows="7">{materialValues(material).body_md ?? material.body_md ?? ""}</textarea>
                    </label>
                  {:else}
                    <label class="workspace-field">
                      <span>Alternativtext</span>
                      <input name="alt_text" type="text" value={materialValues(material).alt_text ?? material.alt_text ?? ""} />
                    </label>
                    <div class="workspace-node-editor-file-actions">
                      <a class="workspace-link-action" href={fileHref(material, "inline")} target="_blank" rel="noreferrer">Vorschau öffnen</a>
                      <a class="workspace-link-action" href={fileHref(material, "attachment")} target="_blank" rel="noreferrer">Herunterladen</a>
                    </div>
                  {/if}

                  {#if materialError(material)}
                    <p class="workspace-note workspace-note--error">{materialError(material)}</p>
                  {/if}

                  <div class="workspace-node-editor-card-actions">
                    <button class="workspace-link-action" type="submit">Speichern</button>
                  </div>
                </form>
              </div>
            {/if}
          </article>
        {/each}
      {/snippet}
    </TeacherNodeEditorSection>

    <TeacherNodeEditorSection
      eyebrow="Aufgaben"
      title="Aufgaben"
      createLabel="Aufgabe hinzufügen"
      showCreate={showCreateTask}
      hasItems={editorState.tasks.length > 0}
      emptyMessage="Noch keine Aufgaben hinterlegt."
      onCreate={openCreateTask}
    >
      {#snippet create()}
        <form method="POST" action="?/createTask" class="workspace-node-editor-card-form" use:enhance={enhanceEditorForm}>
          <input type="hidden" name="section_id" value={sectionId()} />

          <label class="workspace-field">
            <span>Aufgabentyp</span>
            <select bind:value={createTaskKind} name="task_kind">
              <option value="native">Normale Aufgabe</option>
              <option value="h5p">H5P</option>
              <option value="visual">Visuelle Aufgabe</option>
              <option value="scratch">Scratch</option>
              <option value="calliope">Calliope</option>
            </select>
          </label>

          {#if createTaskKind === "h5p"}
            <p class="workspace-note">
              Es wird zunächst eine H5P-Aufgabe angelegt. Den eigentlichen H5P-Inhalt bearbeitest du danach in der aufgeklappten Karte.
            </p>
          {:else}
            <label class="workspace-field">
              <span>Anweisung & Beschreibung</span>
              <textarea name="instruction_md" rows="7">{createTaskValues().instruction_md ?? ""}</textarea>
            </label>

            <fieldset class="workspace-field teacher-node-editor-criteria-fieldset">
              <legend>Kriterien</legend>
              <div class="teacher-node-editor-criteria-list">
                {#each criteriaSlots(createCriteriaItems()) as criterion, index}
                  <label class="workspace-field">
                    <span>Kriterium {index + 1}</span>
                    <input name="criteria[]" type="text" value={criterion} />
                  </label>
                {/each}
              </div>
            </fieldset>

            <label class="workspace-field">
              <span>Lehrkraft-Kontext</span>
              <textarea name="teacher_context_md" rows="4">{createTaskValues().teacher_context_md ?? ""}</textarea>
            </label>
          {/if}

          <div class="workspace-node-editor-grid">
            <label class="workspace-field">
              <span>Fällig bis</span>
              <input name="due_at" type="datetime-local" value={createTaskValues().due_at ?? ""} />
            </label>

            <label class="workspace-field">
              <span>Max. Versuche</span>
              <input name="max_attempts" min="1" type="number" value={createTaskValues().max_attempts ?? ""} />
            </label>
          </div>

          <input name="h5p_content_id" type="hidden" value={createTaskValues().h5p_content_id ?? ""} />

          {#if form?.createTask?.error}
            <p class="workspace-note workspace-note--error">{form.createTask.error}</p>
          {/if}

          <div class="workspace-node-editor-card-actions">
            <button class="workspace-link-action" type="submit">Aufgabe hinzufügen</button>
          </div>
        </form>
      {/snippet}

      {#snippet list()}
        {#each editorState.tasks as task, index}
          <article class:workspace-node-editor-card--expanded={expandedTaskId === task.id} class="workspace-node-editor-card workspace-node-editor-entry workspace-node-editor-entry--task">
            <button class="workspace-node-editor-entry-summary" type="button" onclick={() => toggleTask(task.id)}>
              <div class="workspace-node-editor-entry-summary-bar"></div>
              <div class="workspace-node-editor-entry-summary-copy">
                <p class="workspace-node-editor-entry-kicker">{taskKindLabel(task)}</p>
                <h3>{taskTitle(task, index)}</h3>
                <p class="workspace-node-editor-entry-meta">{taskMeta(task)}</p>
              </div>
              <span aria-hidden="true" class="workspace-node-editor-entry-toggle">{expandedTaskId === task.id ? "−" : "+"}</span>
            </button>

            {#if expandedTaskId === task.id}
              <div class="workspace-node-editor-entry-body">
                <div class="workspace-node-editor-entry-toolbar">
                  <span class="workspace-node-editor-entry-toolbar-spacer"></span>
                  <details class="workspace-node-editor-card-menu">
                    <summary class="workspace-node-editor-card-menu__toggle">Aktionen</summary>
                    <div class="workspace-node-editor-card-menu__panel">
                      <form method="POST" action="?/reorderTask" use:enhance={enhanceEditorForm}>
                        <input type="hidden" name="task_id" value={task.id} />
                        <input type="hidden" name="direction" value="up" />
                        <button type="submit">Nach oben</button>
                      </form>
                      <form method="POST" action="?/reorderTask" use:enhance={enhanceEditorForm}>
                        <input type="hidden" name="task_id" value={task.id} />
                        <input type="hidden" name="direction" value="down" />
                        <button type="submit">Nach unten</button>
                      </form>
                      <form method="POST" action="?/deleteTask" use:enhance={enhanceEditorForm}>
                        <input type="hidden" name="section_id" value={sectionId()} />
                        <input type="hidden" name="task_id" value={task.id} />
                        <button class="workspace-node-editor-card-menu__danger" type="submit">Entfernen</button>
                      </form>
                    </div>
                  </details>
                </div>

                <form method="POST" action="?/saveTask" class="workspace-node-editor-card-form" use:enhance={enhanceEditorForm}>
                  <input type="hidden" name="section_id" value={sectionId()} />
                  <input type="hidden" name="task_id" value={task.id} />
                  <input type="hidden" name="task_kind" value={task.kind} />

                  {#if task.kind === "h5p"}
                    <input type="hidden" name="instruction_md" value={taskInstructionValue(task)} />
                    <input type="hidden" name="h5p_content_id" value={task.h5p?.content_id ?? ""} />
                    <p class="workspace-note">Diese Aufgabe wird direkt im H5P-Editor gepflegt.</p>
                    <TeacherH5PTaskEditor
                      unitId={editorState.unit.id}
                      sectionId={sectionId()}
                      taskId={task.id}
                      contentId={task.h5p?.content_id ?? null}
                    />
                  {:else}
                    <label class="workspace-field">
                      <span>Anweisung & Beschreibung</span>
                      <textarea name="instruction_md" rows="7">{taskInstructionValue(task)}</textarea>
                    </label>

                    <fieldset class="workspace-field teacher-node-editor-criteria-fieldset">
                      <legend>Kriterien</legend>
                      <div class="teacher-node-editor-criteria-list">
                        {#each criteriaSlots(taskCriteriaItems(task)) as criterion, index}
                          <label class="workspace-field">
                            <span>Kriterium {index + 1}</span>
                            <input name="criteria[]" type="text" value={criterion} />
                          </label>
                        {/each}
                      </div>
                    </fieldset>

                    <label class="workspace-field">
                      <span>Lehrkraft-Kontext</span>
                      <textarea name="teacher_context_md" rows="4">{taskTeacherContextValue(task)}</textarea>
                    </label>

                    {#if task.kind === "visual" || task.kind === "scratch" || task.kind === "calliope"}
                      <p class="workspace-note">
                        {#if task.kind === "visual"}
                          Lernende reichen hier eine visuelle Datei ein.
                        {:else if task.kind === "scratch"}
                          Lernende reichen hier ein Scratch-Projekt als `.sb3` ein.
                        {:else}
                          Lernende reichen hier ein Calliope-MakeCode-Projekt als `.hex` ein.
                        {/if}
                      </p>
                    {/if}
                  {/if}

                  <div class="workspace-node-editor-grid">
                    <label class="workspace-field">
                      <span>Fällig bis</span>
                      <input name="due_at" type="datetime-local" value={taskDueAtValue(task)} />
                    </label>

                    <label class="workspace-field">
                      <span>Max. Versuche</span>
                      <input name="max_attempts" type="number" min="1" value={taskMaxAttemptsValue(task)} />
                    </label>
                  </div>

                  {#if taskError(task)}
                    <p class="workspace-note workspace-note--error">{taskError(task)}</p>
                  {/if}

                  <div class="workspace-node-editor-card-actions">
                    <button class="workspace-link-action" type="submit">Speichern</button>
                  </div>
                </form>
              </div>
            {/if}
          </article>
        {/each}
      {/snippet}
    </TeacherNodeEditorSection>
  </section>
</div>
