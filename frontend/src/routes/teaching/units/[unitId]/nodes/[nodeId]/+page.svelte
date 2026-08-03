<script lang="ts">
  import { enhance } from "$app/forms";
  import { tick } from "svelte";

  import { prepareBrowserStorageUpload } from "$lib/utils/browser-storage-upload";
  import { renderMarkdown } from "$lib/utils/markdown";
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
    intent_id: string;
    sha256: string;
  };

  type TaskFormValues = {
    task_kind: string;
    instruction_md: string;
    criteria_items: string[];
    teacher_context_md: string;
    due_at: string;
    max_attempts: string;
    h5p_content_id: string;
    dialog_partner_name: string;
    dialog_partner_description_md: string;
    dialog_role_md: string;
    dialog_learning_goal_md: string;
    dialog_opening_message_md: string;
    dialog_response_mode: string;
    dialog_max_rounds: string;
    dialog_closing_prompt_md: string;
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

  function actionError(value: unknown): string | null {
    if (!value || typeof value !== "object") {
      return null;
    }
    const candidate = value as { error?: unknown };
    return typeof candidate.error === "string" ? candidate.error : null;
  }

  function actionMaterialId(value: unknown): string | null {
    if (!value || typeof value !== "object") {
      return null;
    }
    const candidate = value as { material_id?: unknown };
    return typeof candidate.material_id === "string" ? candidate.material_id : null;
  }

  function actionTaskId(value: unknown): string | null {
    if (!value || typeof value !== "object") {
      return null;
    }
    const candidate = value as { task_id?: unknown };
    return typeof candidate.task_id === "string" ? candidate.task_id : null;
  }

  function sectionId(): string {
    return editorState.node.backing_section_id ?? editorState.node.id;
  }

  let editorOverride = $state<TeacherUnitNodeEditorView | null>(null);
  const editorState = $derived(editorOverride ?? data.editor);
  let expandedMaterialId = $state<string | null>(null);
  let expandedTaskId = $state<string | null>(null);
  let showCreateMaterial = $state(false);
  let showCreateTask = $state(false);
  let createMaterialKind = $state<"markdown" | "file">("markdown");
  let createTaskKind = $state<"native" | "h5p" | "visual" | "scratch" | "calliope" | "filius" | "dialog">("native");
  let handledForm: ActionData | undefined = undefined;
  let createMaterialCard = $state<HTMLElement | null>(null);
  let createTaskCard = $state<HTMLElement | null>(null);
  let createMaterialForm = $state<HTMLFormElement | null>(null);
  let preparedMaterialUploadName = $state<string | null>(null);
  let createMaterialClientError = $state<string | null>(null);
  let createMaterialUploadPending = $state(false);
  let editorMessage = $state<{ tone: "success"; text: string } | null>(null);
  let dialogPreviewInputs = $state<Record<string, string>>({});
  let dialogPreviews = $state<Record<string, { pending: boolean; error: string | null; reply: string | null; starters: string[] }>>({});

  async function previewDialog(task: TeacherUnitNodeEditorTask) {
    const studentMessage = (dialogPreviewInputs[task.id] ?? "").trim();
    if (!studentMessage) return;
    dialogPreviews[task.id] = { pending: true, error: null, reply: null, starters: [] };
    try {
      const response = await fetch(`/api/teaching/units/${encodeURIComponent(editorState.unit.id)}/tasks/${encodeURIComponent(task.id)}/dialog-preview`, {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ operation: "reply", messages: [], student_message_md: studentMessage })
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || "Vorschau nicht verfügbar");
      dialogPreviews[task.id] = { pending: false, error: null, reply: payload.reply_md ?? null, starters: payload.sentence_starters ?? [] };
    } catch (caught) {
      dialogPreviews[task.id] = { pending: false, error: caught instanceof Error ? caught.message : "Vorschau nicht verfügbar", reply: null, starters: [] };
    }
  }

  const enhanceEditorForm = () => {
    return async ({ update }: { update: (options?: { reset?: boolean; invalidateAll?: boolean }) => Promise<void> }) => {
      await update({ reset: false, invalidateAll: false });
    };
  };

  function clearPreparedMaterialUpload() {
    const intentInput = createMaterialForm?.querySelector('input[name="intent_id"]') as HTMLInputElement | null;
    const shaInput = createMaterialForm?.querySelector('input[name="sha256"]') as HTMLInputElement | null;

    if (intentInput) {
      intentInput.value = "";
    }
    if (shaInput) {
      shaInput.value = "";
    }

    preparedMaterialUploadName = null;
    createMaterialClientError = null;
  }

  function createMaterialIntentUrl(): string {
    return `/api/teaching/units/${editorState.unit.id}/sections/${sectionId()}/materials/upload-intents`;
  }

  function createMaterialClientUploadError(reason: string): string {
    if (reason === "mime_not_allowed") {
      return "Dateiformat nicht erlaubt. Erlaubt sind PDF, PNG und JPEG.";
    }
    if (reason === "size_exceeded") {
      return "Datei zu groß. Bitte das Größenlimit beachten.";
    }
    return "Die Datei konnte nicht hochgeladen werden.";
  }

  async function handleCreateMaterialSubmit(event: SubmitEvent) {
    if (createMaterialKind !== "file") {
      createMaterialClientError = null;
      return;
    }

    const formElement = event.currentTarget as HTMLFormElement | null;
    if (!formElement) {
      return;
    }

    const intentInput = formElement.querySelector('input[name="intent_id"]') as HTMLInputElement | null;
    const shaInput = formElement.querySelector('input[name="sha256"]') as HTMLInputElement | null;
    if ((intentInput?.value || "").trim() && (shaInput?.value || "").trim()) {
      return;
    }

    const fileInput = formElement.querySelector('input[name="upload_file"]') as HTMLInputElement | null;
    const file = fileInput?.files?.[0];
    if (!file) {
      preparedMaterialUploadName = null;
      createMaterialClientError = null;
      return;
    }

    event.preventDefault();
    createMaterialUploadPending = true;
    createMaterialClientError = null;

    try {
      const mimeType = String(file.type || "").trim().toLowerCase() || "application/octet-stream";
      const prepared = await prepareBrowserStorageUpload({
        intentUrl: createMaterialIntentUrl(),
        intentPayload: {
          filename: file.name || "material.bin",
          mime_type: mimeType,
          size_bytes: file.size
        },
        file,
        fallbackMimeType: mimeType
      });

      if (intentInput) {
        intentInput.value = prepared.intent.intent_id;
      }
      if (shaInput) {
        shaInput.value = prepared.sha256;
      }
      if (fileInput) {
        fileInput.value = "";
      }

      preparedMaterialUploadName = file.name || "Datei";
      formElement.requestSubmit();
    } catch (caught) {
      clearPreparedMaterialUpload();
      const reason = caught instanceof Error ? caught.message : "upload_failed";
      createMaterialClientError = createMaterialClientUploadError(reason);
    } finally {
      createMaterialUploadPending = false;
    }
  }

  function handleCreateMaterialFileChange() {
    clearPreparedMaterialUpload();
  }

  function materialValues(material: TeacherUnitNodeEditorMaterial): Partial<MaterialFormValues> {
    const saveMaterial = form?.saveMaterial;
    if (actionMaterialId(saveMaterial) !== material.id) {
      return {};
    }
    return actionValues<MaterialFormValues>(saveMaterial);
  }

  function materialError(material: TeacherUnitNodeEditorMaterial): string | null {
    return actionMaterialId(form?.saveMaterial) === material.id ? actionError(form?.saveMaterial) : null;
  }

  function taskValues(task: TeacherUnitNodeEditorTask): Partial<TaskFormValues> {
    const saveTask = form?.saveTask;
    if (actionTaskId(saveTask) !== task.id) {
      return {};
    }
    return actionValues<TaskFormValues>(saveTask);
  }

  function taskError(task: TeacherUnitNodeEditorTask): string | null {
    return actionTaskId(form?.saveTask) === task.id ? actionError(form?.saveTask) : null;
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
    return actionError(form?.saveNode);
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
      case "filius":
        return "Filius";
      case "dialog":
        return "KI-Dialog";
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
    data.editor;
    editorOverride = null;
    expandedMaterialId = null;
    expandedTaskId = null;
    showCreateMaterial = data.editor.materials.length === 0;
    showCreateTask = data.editor.tasks.length === 0;
    createMaterialKind = "markdown";
    createTaskKind = "native";
    handledForm = undefined;
    preparedMaterialUploadName = null;
    createMaterialClientError = null;
    createMaterialUploadPending = false;
    editorMessage = null;
  });

  $effect(() => {
    const materialKind = createMaterialValues().material_kind;
    if (materialKind === "file" || materialKind === "markdown") {
      createMaterialKind = materialKind;
    }
  });

  $effect(() => {
    if (createMaterialKind !== "file") {
      clearPreparedMaterialUpload();
      createMaterialUploadPending = false;
    }
  });

  $effect(() => {
    const taskKind = createTaskValues().task_kind;
    if (taskKind === "h5p" || taskKind === "visual" || taskKind === "scratch" || taskKind === "calliope" || taskKind === "filius" || taskKind === "dialog") {
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
    const saveNodeSuccess = asSuccess(form.saveNode);
    const saveTaskSuccess = asSuccess(form.saveTask);
    const createTaskSuccess = asSuccess(form.createTask);
    const deleteTaskSuccess = asSuccess(form.deleteTask);
    const reorderTaskSuccess = asSuccess(form.reorderTask);

    const success =
      saveNodeSuccess
      ?? saveMaterialSuccess
      ?? createMaterialSuccess
      ?? deleteMaterialSuccess
      ?? reorderMaterialSuccess
      ?? saveTaskSuccess
      ?? createTaskSuccess
      ?? deleteTaskSuccess
      ?? reorderTaskSuccess;

    if (success) {
      editorOverride = plainEditor(success.editor);
      editorMessage = success.message ? { text: success.message, tone: "success" } : null;
      if (saveMaterialSuccess || reorderMaterialSuccess) {
        expandedMaterialId = success.material_id ?? expandedMaterialId;
      } else if (createMaterialSuccess) {
        expandedMaterialId = success.material_id ?? success.editor.materials.at(-1)?.id ?? null;
        showCreateMaterial = false;
        clearPreparedMaterialUpload();
        createMaterialUploadPending = false;
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

    if (actionError(form.saveNode)) {
      editorMessage = null;
    }
    const saveMaterialId = actionMaterialId(form.saveMaterial);
    if (saveMaterialId) {
      editorMessage = null;
      expandedMaterialId = saveMaterialId;
    }
    const saveTaskId = actionTaskId(form.saveTask);
    if (saveTaskId) {
      editorMessage = null;
      expandedTaskId = saveTaskId;
    }
    if (actionError(form.createMaterial)) {
      editorMessage = null;
      showCreateMaterial = true;
      if (!createMaterialValues().intent_id || !createMaterialValues().sha256) {
        preparedMaterialUploadName = null;
      }
    }
    if (actionError(form.createTask)) {
      editorMessage = null;
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
    {#if editorMessage}
      <p class={`workspace-note workspace-note--success teacher-flow-status teacher-flow-status--${editorMessage.tone}`}>
        {editorMessage.text}
      </p>
    {/if}

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
        <form
          method="POST"
          action="?/createMaterial"
          enctype="multipart/form-data"
          class="workspace-node-editor-card-form"
          bind:this={createMaterialForm}
          use:enhance={enhanceEditorForm}
          onsubmit={handleCreateMaterialSubmit}
        >
          <input type="hidden" name="section_id" value={sectionId()} />
          <input name="intent_id" type="hidden" value={createMaterialValues().intent_id ?? ""} />
          <input name="sha256" type="hidden" value={createMaterialValues().sha256 ?? ""} />

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
              <input name="upload_file" type="file" onchange={handleCreateMaterialFileChange} />
            </label>
            {#if createMaterialUploadPending}
              <p class="workspace-note">Datei wird hochgeladen und vorbereitet …</p>
            {:else if preparedMaterialUploadName}
              <p class="workspace-note">Datei vorbereitet: {preparedMaterialUploadName}</p>
            {/if}
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

          {#if createMaterialClientError}
            <p class="workspace-note workspace-note--error">{createMaterialClientError}</p>
          {/if}

          {#if actionError(form?.createMaterial)}
            <p class="workspace-note workspace-note--error">{actionError(form?.createMaterial)}</p>
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
              <option value="filius">Filius</option>
              <option value="dialog">KI-Dialog</option>
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

            {#if createTaskKind === "dialog"}
              <p class="workspace-note">Interne Rolle, Lernziel und Lehrkraft-Kontext werden Lernenden nicht angezeigt.</p>
              <div class="workspace-node-editor-grid">
                <label class="workspace-field"><span>Name des KI-Partners</span><input name="dialog_partner_name" maxlength="120" value={createTaskValues().dialog_partner_name ?? ""} /></label>
                <label class="workspace-field"><span>Antwortmodus</span><select name="dialog_response_mode" value={createTaskValues().dialog_response_mode ?? "free_text"}><option value="free_text">Freitext</option><option value="hybrid">Freitext mit Satzanfängen</option></select></label>
              </div>
              <label class="workspace-field"><span>Sichtbare Kurzbeschreibung</span><textarea name="dialog_partner_description_md" rows="3">{createTaskValues().dialog_partner_description_md ?? ""}</textarea></label>
              <label class="workspace-field"><span>Interne Rolleninstruktion</span><textarea name="dialog_role_md" rows="4">{createTaskValues().dialog_role_md ?? ""}</textarea></label>
              <label class="workspace-field"><span>Internes Lernziel</span><textarea name="dialog_learning_goal_md" rows="3">{createTaskValues().dialog_learning_goal_md ?? ""}</textarea></label>
              <label class="workspace-field"><span>Eröffnungsnachricht</span><textarea name="dialog_opening_message_md" rows="3">{createTaskValues().dialog_opening_message_md ?? ""}</textarea></label>
              <div class="workspace-node-editor-grid">
                <label class="workspace-field"><span>Max. Schülerantworten</span><input name="dialog_max_rounds" min="1" max="12" type="number" value={createTaskValues().dialog_max_rounds ?? "8"} /></label>
              </div>
              <label class="workspace-field"><span>Optionaler Abschlussauftrag</span><textarea name="dialog_closing_prompt_md" rows="3">{createTaskValues().dialog_closing_prompt_md ?? ""}</textarea></label>
            {/if}
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

          {#if actionError(form?.createTask)}
            <p class="workspace-note workspace-note--error">{actionError(form?.createTask)}</p>
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

                    {#if task.kind === "dialog"}
                      <p class="workspace-note">Interne Rolle, Lernziel und Lehrkraft-Kontext werden Lernenden nicht angezeigt. Die Vorschau nutzt die zuletzt gespeicherte Fassung.</p>
                      <div class="workspace-node-editor-grid">
                        <label class="workspace-field"><span>Name des KI-Partners</span><input name="dialog_partner_name" maxlength="120" value={taskValues(task).dialog_partner_name ?? task.dialog?.partner_name ?? ""} /></label>
                        <label class="workspace-field"><span>Antwortmodus</span><select name="dialog_response_mode" value={taskValues(task).dialog_response_mode ?? task.dialog?.response_mode ?? "free_text"}><option value="free_text">Freitext</option><option value="hybrid">Freitext mit Satzanfängen</option></select></label>
                      </div>
                      <label class="workspace-field"><span>Sichtbare Kurzbeschreibung</span><textarea name="dialog_partner_description_md" rows="3">{taskValues(task).dialog_partner_description_md ?? task.dialog?.partner_description_md ?? ""}</textarea></label>
                      <label class="workspace-field"><span>Interne Rolleninstruktion</span><textarea name="dialog_role_md" rows="4">{taskValues(task).dialog_role_md ?? task.dialog?.role_md ?? ""}</textarea></label>
                      <label class="workspace-field"><span>Internes Lernziel</span><textarea name="dialog_learning_goal_md" rows="3">{taskValues(task).dialog_learning_goal_md ?? task.dialog?.learning_goal_md ?? ""}</textarea></label>
                      <label class="workspace-field"><span>Eröffnungsnachricht</span><textarea name="dialog_opening_message_md" rows="3">{taskValues(task).dialog_opening_message_md ?? task.dialog?.opening_message_md ?? ""}</textarea></label>
                      <label class="workspace-field"><span>Max. Schülerantworten</span><input name="dialog_max_rounds" min="1" max="12" type="number" value={taskValues(task).dialog_max_rounds ?? String(task.dialog?.max_rounds ?? 8)} /></label>
                      <label class="workspace-field"><span>Optionaler Abschlussauftrag</span><textarea name="dialog_closing_prompt_md" rows="3">{taskValues(task).dialog_closing_prompt_md ?? task.dialog?.closing_prompt_md ?? ""}</textarea></label>
                      <details class="workspace-note" aria-label="Dialogvorschau">
                        <summary>Gespeicherte Konfiguration testen</summary>
                        <p>Die Vorschau wird nicht gespeichert. Speichere Änderungen zuerst.</p>
                        <label class="workspace-field"><span>Probeantwort eines Schülers</span><textarea rows="3" value={dialogPreviewInputs[task.id] ?? ""} oninput={(event) => (dialogPreviewInputs[task.id] = event.currentTarget.value)}></textarea></label>
                        <button class="workspace-link-action" type="button" disabled={dialogPreviews[task.id]?.pending || !(dialogPreviewInputs[task.id] ?? "").trim()} onclick={() => previewDialog(task)}>KI-Antwort testen</button>
                        {#if dialogPreviews[task.id]?.error}<p class="workspace-note workspace-note--error">{dialogPreviews[task.id].error}</p>{/if}
                        {#if dialogPreviews[task.id]?.reply}<div class="markdown-prose">{@html renderMarkdown(dialogPreviews[task.id].reply ?? "")}</div>{/if}
                        {#if dialogPreviews[task.id]?.starters.length}<p>Satzanfänge: {dialogPreviews[task.id].starters.join(" · ")}</p>{/if}
                      </details>
                    {/if}

                    {#if task.kind === "visual" || task.kind === "scratch" || task.kind === "calliope" || task.kind === "filius"}
                      <p class="workspace-note">
                        {#if task.kind === "visual"}
                          Lernende reichen hier eine visuelle Datei ein.
                        {:else if task.kind === "scratch"}
                          Lernende reichen hier ein Scratch-Projekt als `.sb3` ein.
                        {:else if task.kind === "calliope"}
                          Lernende reichen hier ein Calliope-MakeCode-Projekt als `.hex` ein.
                        {:else}
                          Lernende reichen hier ein Filius-Projekt als `.fls` ein.
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
