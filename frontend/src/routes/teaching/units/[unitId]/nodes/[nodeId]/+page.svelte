<script lang="ts">
  import { enhance } from "$app/forms";
  import { browser } from "$app/environment";
  import { replaceState } from "$app/navigation";
  import { onMount, tick } from "svelte";

  import { prepareBrowserStorageUpload } from "$lib/utils/browser-storage-upload";
  import { renderMarkdown } from "$lib/utils/markdown";
  import GraphDeleteDialog from "$lib/components/teacher-unit-graph/GraphDeleteDialog.svelte";
  import ContentDeleteDialog from "$lib/components/teacher-node-editor/ContentDeleteDialog.svelte";
  import TeacherCriteriaEditor from "$lib/components/teacher-node-editor/TeacherCriteriaEditor.svelte";
  import TeacherH5PTaskEditor from "$lib/components/TeacherH5PTaskEditor.svelte";
  import TeacherNodeEditorProperties from "$lib/components/teacher-node-editor/TeacherNodeEditorProperties.svelte";
  import TeacherNodeEditorSection from "$lib/components/teacher-node-editor/TeacherNodeEditorSection.svelte";
  import PageActionHead from "$lib/components/ui/PageActionHead.svelte";
  import MarkdownEditor from "$lib/components/ui/MarkdownEditor.svelte";
  import {
    contentSelectionParam,
    draftStorageKey,
    formatPrerequisiteSummary,
    type ModuleContentSelection
  } from "$lib/teacher-node-editor/module-content-state";
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
  let createMaterialSelectedFile = $state<File | null>(null);
  let editorMessage = $state<{ tone: "success" | "error"; text: string } | null>(null);
  let dialogPreviewInputs = $state<Record<string, string>>({});
  let dialogPreviews = $state<Record<string, { pending: boolean; error: string | null; reply: string | null; starters: string[] }>>({});
  let deleteModuleOpen = $state(false);
  let deleteContentTarget = $state<{ kind: "material" | "task"; id: string; title: string } | null>(null);
  let moduleSelection = $state<ModuleContentSelection>({ kind: "overview" });
  let draftTargets = $state<string[]>([]);
  let restoredDraftValues = $state<Record<string, Record<string, string | string[]>>>({});
  let draggedContent = $state<{ kind: "material" | "task"; id: string } | null>(null);
  let materialDropForm = $state<HTMLFormElement | null>(null);
  let taskDropForm = $state<HTMLFormElement | null>(null);
  let dropBeforeId = $state("");

  const isModuleEditor = $derived(editorState.node.kind === "module");
  const prerequisiteSummary = $derived(
    formatPrerequisiteSummary(
      editorState.settings.kind === "module" ? editorState.settings.required_prereq_count : 0,
      data.incomingPrerequisiteCount ?? 0
    )
  );

  function replaceContentUrl(selection: ModuleContentSelection) {
    if (!browser) return;
    const next = new URL(window.location.href);
    const value = contentSelectionParam(selection);
    if (value) next.searchParams.set("content", value);
    else next.searchParams.delete("content");
    replaceState(`${next.pathname}${next.search}${next.hash}`, window.history.state);
  }

  function selectModuleContent(selection: ModuleContentSelection) {
    moduleSelection = selection;
    expandedMaterialId = selection.kind === "material" ? selection.id : null;
    expandedTaskId = selection.kind === "task" ? selection.id : null;
    showCreateMaterial = selection.kind === "new-material";
    showCreateTask = selection.kind === "new-task";
    editorMessage = null;
    replaceContentUrl(selection);
    if (browser && isModuleEditor) {
      if (selection.kind === "new-material" || selection.kind === "new-task") {
        sessionStorage.setItem(moduleSelectionStorageKey(), selection.kind);
      } else {
        sessionStorage.removeItem(moduleSelectionStorageKey());
      }
      const target = selectionDraftTarget(selection);
      if (target) void restoreModuleDraft(target);
    }
  }

  function moduleContentSelected(kind: "material" | "task", id: string): boolean {
    return moduleSelection.kind === kind && moduleSelection.id === id;
  }

  function selectionDraftTarget(selection = moduleSelection): string | null {
    if (selection.kind === "overview") return null;
    if (selection.kind === "new-material" || selection.kind === "new-task") return selection.kind;
    return `${selection.kind}:${selection.id}`;
  }

  function moduleDraftKey(target: string): string {
    return draftStorageKey({
      teacherSub: editorState.user.sub,
      unitId: editorState.unit.id,
      nodeId: editorState.node.id,
      target
    });
  }

  function moduleSelectionStorageKey(): string {
    return `${moduleDraftKey("selection")}:active`;
  }

  function readDraft(target: string): Record<string, string | string[]> | null {
    if (!browser) return null;
    try {
      const raw = sessionStorage.getItem(moduleDraftKey(target));
      return raw ? JSON.parse(raw) as Record<string, string | string[]> : null;
    } catch {
      return null;
    }
  }

  function collectDraftTargets() {
    if (!browser || !isModuleEditor) return;
    const prefix = draftStorageKey({
      teacherSub: editorState.user.sub,
      unitId: editorState.unit.id,
      nodeId: editorState.node.id,
      target: ""
    });
    draftTargets = Array.from({ length: sessionStorage.length }, (_, index) => sessionStorage.key(index))
      .filter((key): key is string => Boolean(key?.startsWith(prefix) && !key.endsWith(":active")))
      .map((key) => decodeURIComponent(key.slice(prefix.length)));
    restoredDraftValues = Object.fromEntries(
      draftTargets.flatMap((target) => {
        const values = readDraft(target);
        return values ? [[target, values] as const] : [];
      })
    );
  }

  function hasDraft(target: string): boolean {
    return draftTargets.includes(target);
  }

  function captureModuleDraft(event: Event) {
    if (!browser || !isModuleEditor) return;
    const formElement = event.currentTarget as HTMLFormElement;
    const target = formElement.dataset.draftTarget;
    if (!target) return;
    const values: Record<string, string | string[]> = {};
    const formData = new FormData(formElement);
    for (const [name, entry] of formData.entries()) {
      if (entry instanceof File || ["section_id", "material_id", "task_id", "intent_id", "sha256"].includes(name)) continue;
      const current = values[name];
      if (current === undefined) values[name] = entry;
      else values[name] = Array.isArray(current) ? [...current, entry] : [current, entry];
    }
    sessionStorage.setItem(moduleDraftKey(target), JSON.stringify(values));
    if (!draftTargets.includes(target)) draftTargets = [...draftTargets, target];
  }

  function captureMarkdownDraft(target: string, name: "body_md" | "instruction_md", value: string) {
    if (!browser || !isModuleEditor) return;
    const values = readDraft(target) ?? {};
    values[name] = value;
    sessionStorage.setItem(moduleDraftKey(target), JSON.stringify(values));
    if (!draftTargets.includes(target)) draftTargets = [...draftTargets, target];
  }

  function restoredDraftText(target: string, name: string, fallback: string): string {
    const value = restoredDraftValues[target]?.[name];
    if (Array.isArray(value)) return value[0] ?? fallback;
    return value ?? fallback;
  }

  function restoredDraftList(target: string, name: string, fallback: string[]): string[] {
    const value = restoredDraftValues[target]?.[name];
    if (Array.isArray(value)) return value;
    if (typeof value === "string") return [value];
    return fallback;
  }

  async function restoreModuleDraft(target: string) {
    if (!browser || !isModuleEditor) return;
    const values = readDraft(target);
    if (!values) return;
    restoredDraftValues = { ...restoredDraftValues, [target]: values };
    await tick();
    const formElement = Array.from(document.querySelectorAll<HTMLFormElement>("form[data-draft-target]"))
      .find((formItem) => formItem.dataset.draftTarget === target);
    if (!formElement) return;
    for (const [name, stored] of Object.entries(values)) {
      if (name === "body_md" || name === "instruction_md" || name === "criteria[]") continue;
      const controls = Array.from(formElement.elements).filter((control): control is HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement =>
        control instanceof HTMLInputElement || control instanceof HTMLTextAreaElement || control instanceof HTMLSelectElement
      ).filter((control) => control.name === name);
      const entries = Array.isArray(stored) ? stored : [stored];
      controls.forEach((control, index) => {
        if (control instanceof HTMLInputElement && control.type === "file") return;
        control.value = entries[index] ?? entries[0] ?? "";
        control.dispatchEvent(new Event("input", { bubbles: true }));
        control.dispatchEvent(new Event("change", { bubbles: true }));
      });
    }
  }

  function clearModuleDraft(target: string) {
    if (!browser) return;
    sessionStorage.removeItem(moduleDraftKey(target));
    draftTargets = draftTargets.filter((item) => item !== target);
    const nextValues = { ...restoredDraftValues };
    delete nextValues[target];
    restoredDraftValues = nextValues;
  }

  async function discardCurrentDraft() {
    const target = selectionDraftTarget();
    if (!target) return;
    const current = moduleSelection;
    clearModuleDraft(target);
    if (target === "new-material") createMaterialSelectedFile = null;
    moduleSelection = { kind: "overview" };
    await tick();
    selectModuleContent(current);
  }

  onMount(() => {
    let active = true;
    void (async () => {
      await tick();
      if (!active) return;
      collectDraftTargets();
      const target = selectionDraftTarget();
      if (target) await restoreModuleDraft(target);
    })();
    return () => {
      active = false;
    };
  });

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
    const file = fileInput?.files?.[0] ?? createMaterialSelectedFile;
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

  function handleCreateMaterialFileChange(event: Event) {
    clearPreparedMaterialUpload();
    createMaterialSelectedFile = (event.currentTarget as HTMLInputElement).files?.[0] ?? null;
  }

  function restoreCreateMaterialFile() {
    if (!createMaterialSelectedFile || !createMaterialForm || typeof DataTransfer === "undefined") return;
    const fileInput = createMaterialForm.querySelector<HTMLInputElement>('input[name="upload_file"]');
    if (!fileInput || fileInput.files?.length) return;
    const transfer = new DataTransfer();
    transfer.items.add(createMaterialSelectedFile);
    fileInput.files = transfer.files;
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

  function materialOutlineMeta(material: TeacherUnitNodeEditorMaterial): string {
    if (material.kind === "markdown") return "Textmaterial";
    const details = materialMeta(material);
    return details ? `Datei · ${details}` : "Datei";
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
    if (isModuleEditor) {
      selectModuleContent({ kind: "new-material" });
      await tick();
      createMaterialCard?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      restoreCreateMaterialFile();
      return;
    }
    showCreateMaterial = !showCreateMaterial;
    expandedMaterialId = null;
    if (!showCreateMaterial) {
      return;
    }
    await tick();
    createMaterialCard?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  async function openCreateTask() {
    if (isModuleEditor) {
      selectModuleContent({ kind: "new-task" });
      await tick();
      createTaskCard?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      return;
    }
    showCreateTask = !showCreateTask;
    expandedTaskId = null;
    if (!showCreateTask) {
      return;
    }
    await tick();
    createTaskCard?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function toggleMaterial(materialId: string) {
    if (isModuleEditor) {
      selectModuleContent({ kind: "material", id: materialId });
      return;
    }
    expandedMaterialId = expandedMaterialId === materialId ? null : materialId;
    showCreateMaterial = false;
  }

  function toggleTask(taskId: string) {
    if (isModuleEditor) {
      selectModuleContent({ kind: "task", id: taskId });
      return;
    }
    expandedTaskId = expandedTaskId === taskId ? null : taskId;
    showCreateTask = false;
  }

  $effect(() => {
    data.editor;
    const dataIsModuleEditor = data.editor.node.kind === "module";
    const selectionKey = `${draftStorageKey({
      teacherSub: data.editor.user.sub,
      unitId: data.editor.unit.id,
      nodeId: data.editor.node.id,
      target: "selection"
    })}:active`;
    const storedSelection = browser && dataIsModuleEditor ? sessionStorage.getItem(selectionKey) : null;
    const initialSelection: ModuleContentSelection = data.contentSelection?.kind === "overview" && (storedSelection === "new-material" || storedSelection === "new-task")
      ? { kind: storedSelection }
      : data.contentSelection ?? { kind: "overview" };
    editorOverride = null;
    moduleSelection = initialSelection;
    expandedMaterialId = initialSelection.kind === "material" ? initialSelection.id : null;
    expandedTaskId = initialSelection.kind === "task" ? initialSelection.id : null;
    showCreateMaterial = dataIsModuleEditor ? initialSelection.kind === "new-material" : data.editor.materials.length === 0;
    showCreateTask = dataIsModuleEditor ? initialSelection.kind === "new-task" : data.editor.tasks.length === 0;
    createMaterialKind = "markdown";
    createTaskKind = "native";
    handledForm = undefined;
    preparedMaterialUploadName = null;
    createMaterialClientError = null;
    createMaterialUploadPending = false;
    createMaterialSelectedFile = null;
    restoredDraftValues = {};
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
        if (saveMaterialSuccess && expandedMaterialId) clearModuleDraft(`material:${expandedMaterialId}`);
      } else if (createMaterialSuccess) {
        clearModuleDraft("new-material");
        expandedMaterialId = success.material_id ?? success.editor.materials.at(-1)?.id ?? null;
        showCreateMaterial = false;
        if (isModuleEditor && expandedMaterialId) {
          selectModuleContent({ kind: "material", id: expandedMaterialId });
        }
        clearPreparedMaterialUpload();
        createMaterialSelectedFile = null;
        createMaterialUploadPending = false;
      } else if (deleteMaterialSuccess) {
        if (deleteContentTarget?.kind === "material") clearModuleDraft(`material:${deleteContentTarget.id}`);
        expandedMaterialId = null;
        deleteContentTarget = null;
        if (isModuleEditor) selectModuleContent({ kind: "overview" });
      }

      if (saveTaskSuccess || reorderTaskSuccess) {
        expandedTaskId = success.task_id ?? expandedTaskId;
        if (saveTaskSuccess && expandedTaskId) clearModuleDraft(`task:${expandedTaskId}`);
      } else if (createTaskSuccess) {
        clearModuleDraft("new-task");
        expandedTaskId = success.task_id ?? success.editor.tasks.at(-1)?.id ?? null;
        showCreateTask = false;
        if (isModuleEditor && expandedTaskId) {
          selectModuleContent({ kind: "task", id: expandedTaskId });
        }
      } else if (deleteTaskSuccess) {
        if (deleteContentTarget?.kind === "task") clearModuleDraft(`task:${deleteContentTarget.id}`);
        expandedTaskId = null;
        deleteContentTarget = null;
        if (isModuleEditor) selectModuleContent({ kind: "overview" });
      }
      editorMessage = success.message ? { text: success.message, tone: "success" } : null;
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
      if (isModuleEditor) selectModuleContent({ kind: "new-material" });
      if (!createMaterialValues().intent_id || !createMaterialValues().sha256) {
        preparedMaterialUploadName = null;
      }
    }
    if (actionError(form.createTask)) {
      editorMessage = null;
      showCreateTask = true;
      if (isModuleEditor) selectModuleContent({ kind: "new-task" });
    }
    if (actionError(form.deleteModule)) {
      deleteModuleOpen = true;
    }
    const reorderError = actionError(form.reorderMaterial) ?? actionError(form.reorderTask);
    if (reorderError) {
      editorMessage = { tone: "error", text: reorderError };
    }
  });

  function openDeleteModuleDialog() {
    deleteModuleOpen = true;
  }

  function closeDeleteModuleDialog() {
    deleteModuleOpen = false;
  }

  function openContentDeleteDialog(kind: "material" | "task", id: string, title: string) {
    deleteContentTarget = { kind, id, title };
  }

  function closeContentDeleteDialog() {
    deleteContentTarget = null;
  }

  function startContentDrag(kind: "material" | "task", id: string, event: DragEvent) {
    draggedContent = { kind, id };
    event.dataTransfer?.setData("text/plain", id);
    if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
  }

  async function dropContentBefore(kind: "material" | "task", beforeId: string, event: DragEvent) {
    event.preventDefault();
    if (!draggedContent || draggedContent.kind !== kind || draggedContent.id === beforeId) return;
    dropBeforeId = beforeId;
    await tick();
    (kind === "material" ? materialDropForm : taskDropForm)?.requestSubmit();
    draggedContent = null;
  }
</script>

<svelte:head>
  <title>{editorState.node.editor_title} | GUSTAV</title>
</svelte:head>

{#snippet nodeHeaderActions()}
  {#if editorState.node.kind === "module"}
    <details class="workspace-row-menu">
      <summary aria-label="Modulaktionen">⋯</summary>
      <div class="workspace-row-menu-popover">
        <button class="workspace-link-action workspace-link-action--danger" type="button" onclick={openDeleteModuleDialog}>
          Modul löschen
        </button>
      </div>
    </details>
  {/if}
{/snippet}

<div class="workspace-page teacher-node-editor-page">
  <PageActionHead
    backHref={`/teaching/units/${editorState.unit.id}?module=${encodeURIComponent(editorState.node.id)}&quick=1`}
    backLabel="Zurück zum Graph"
    title={editorState.node.editor_title}
    copy={isModuleEditor
      ? `${editorState.materials.length} ${editorState.materials.length === 1 ? "Material" : "Materialien"} · ${editorState.tasks.length} ${editorState.tasks.length === 1 ? "Aufgabe" : "Aufgaben"} · ${prerequisiteSummary}`
      : null}
    actions={nodeHeaderActions}
  />

  <section
    class:teacher-module-workbench={isModuleEditor}
    class="workspace-node-editor workspace-node-editor--content-only"
    data-module-stage={moduleSelection.kind === "overview" ? "contents" : "editor"}
  >
    {#if editorMessage}
      <p
        class={`workspace-note workspace-note--${editorMessage.tone} teacher-flow-status teacher-flow-status--${editorMessage.tone}`}
        role={editorMessage.tone === "error" ? "alert" : "status"}
      >
        {editorMessage.text}
      </p>
    {/if}

    {#if isModuleEditor}
      <aside class="teacher-module-outline" aria-label="Modulinhalte">
        <div class="teacher-module-outline__head">
          <h2>Inhalte</h2>
        </div>

        <section class="teacher-module-outline__group" aria-labelledby="module-materials-heading">
          <div class="teacher-module-outline__group-head">
            <h3 id="module-materials-heading">Materialien</h3>
            {#if hasDraft("new-material")}<span class="teacher-module-outline__draft">Neuer Entwurf</span>{/if}
            <button
              class:teacher-module-outline__compact-add={moduleSelection.kind === "overview"}
              type="button"
              aria-label={moduleSelection.kind === "overview" ? "Material ergänzen" : "Material hinzufügen"}
              onclick={openCreateMaterial}
            >+</button>
          </div>
          {#if editorState.materials.length}
            <ol>
              {#each editorState.materials as material}
                <li
                  class:teacher-module-outline__row--selected={moduleContentSelected("material", material.id)}
                  draggable="true"
                  ondragstart={(event) => startContentDrag("material", material.id, event)}
                  ondragover={(event) => event.preventDefault()}
                  ondrop={(event) => dropContentBefore("material", material.id, event)}
                >
                  <button class="teacher-module-outline__select" type="button" onclick={() => toggleMaterial(material.id)}>
                    <span class="teacher-module-outline__drag-handle" aria-hidden="true">≡</span>
                    <strong>{material.title}</strong>
                    <span>{materialOutlineMeta(material)}</span>
                    {#if hasDraft(`material:${material.id}`)}<span class="teacher-module-outline__draft">Entwurf</span>{/if}
                  </button>
                  <details class="workspace-row-menu">
                    <summary aria-label={`Aktionen für ${material.title}`}>⋯</summary>
                    <div class="workspace-row-menu-popover">
                      <form method="POST" action="?/reorderMaterial" use:enhance={enhanceEditorForm}>
                        <input type="hidden" name="material_id" value={material.id} />
                        <input type="hidden" name="direction" value="up" />
                        <button class="workspace-text-button" type="submit">Nach oben</button>
                      </form>
                      <form method="POST" action="?/reorderMaterial" use:enhance={enhanceEditorForm}>
                        <input type="hidden" name="material_id" value={material.id} />
                        <input type="hidden" name="direction" value="down" />
                        <button class="workspace-text-button" type="submit">Nach unten</button>
                      </form>
                    </div>
                  </details>
                </li>
              {/each}
            </ol>
            <form class="teacher-module-outline__drop-form" method="POST" action="?/reorderMaterial" use:enhance={enhanceEditorForm} bind:this={materialDropForm}>
              <input type="hidden" name="material_id" value={draggedContent?.kind === "material" ? draggedContent.id : ""} />
              <input type="hidden" name="before_id" value={dropBeforeId} />
            </form>
          {:else}
            <p class="teacher-module-outline__empty">Noch keine Materialien</p>
          {/if}
        </section>

        <section class="teacher-module-outline__group" aria-labelledby="module-tasks-heading">
          <div class="teacher-module-outline__group-head">
            <h3 id="module-tasks-heading">Aufgaben</h3>
            {#if hasDraft("new-task")}<span class="teacher-module-outline__draft">Neuer Entwurf</span>{/if}
            <button
              class:teacher-module-outline__compact-add={moduleSelection.kind === "overview"}
              type="button"
              aria-label={moduleSelection.kind === "overview" ? "Aufgabe ergänzen" : "Aufgabe hinzufügen"}
              onclick={openCreateTask}
            >+</button>
          </div>
          {#if editorState.tasks.length}
            <ol>
              {#each editorState.tasks as task, index}
                <li
                  class:teacher-module-outline__row--selected={moduleContentSelected("task", task.id)}
                  draggable="true"
                  ondragstart={(event) => startContentDrag("task", task.id, event)}
                  ondragover={(event) => event.preventDefault()}
                  ondrop={(event) => dropContentBefore("task", task.id, event)}
                >
                  <button class="teacher-module-outline__select" type="button" onclick={() => toggleTask(task.id)}>
                    <span class="teacher-module-outline__drag-handle" aria-hidden="true">≡</span>
                    <strong>{taskTitle(task, index)}</strong>
                    <span>{taskMeta(task)}</span>
                    {#if hasDraft(`task:${task.id}`)}<span class="teacher-module-outline__draft">Entwurf</span>{/if}
                  </button>
                  <details class="workspace-row-menu">
                    <summary aria-label={`Aktionen für ${taskTitle(task, index)}`}>⋯</summary>
                    <div class="workspace-row-menu-popover">
                      <form method="POST" action="?/reorderTask" use:enhance={enhanceEditorForm}>
                        <input type="hidden" name="task_id" value={task.id} />
                        <input type="hidden" name="direction" value="up" />
                        <button class="workspace-text-button" type="submit">Nach oben</button>
                      </form>
                      <form method="POST" action="?/reorderTask" use:enhance={enhanceEditorForm}>
                        <input type="hidden" name="task_id" value={task.id} />
                        <input type="hidden" name="direction" value="down" />
                        <button class="workspace-text-button" type="submit">Nach unten</button>
                      </form>
                    </div>
                  </details>
                </li>
              {/each}
            </ol>
            <form class="teacher-module-outline__drop-form" method="POST" action="?/reorderTask" use:enhance={enhanceEditorForm} bind:this={taskDropForm}>
              <input type="hidden" name="task_id" value={draggedContent?.kind === "task" ? draggedContent.id : ""} />
              <input type="hidden" name="before_id" value={dropBeforeId} />
            </form>
          {:else}
            <p class="teacher-module-outline__empty">Noch keine Aufgaben</p>
          {/if}
        </section>
      </aside>
    {/if}

    <div class:teacher-module-editor-pane={isModuleEditor}>
      {#if isModuleEditor && moduleSelection.kind !== "overview"}
        <button class="teacher-module-editor-pane__back" type="button" onclick={() => selectModuleContent({ kind: "overview" })}>
          ← Inhalte
        </button>
      {/if}
      {#if !isModuleEditor}
        <TeacherNodeEditorProperties
          node={editorState.node}
          settings={editorState.settings}
          values={saveNodeValues()}
          error={saveNodeError()}
        />
      {:else if moduleSelection.kind === "overview"}
        <section class="teacher-module-editor-overview">
          <p class="workspace-label">Modulinhalt</p>
          <h2>Inhalt auswählen</h2>
          <p>Wähle links ein Material oder eine Aufgabe aus.</p>
          <div class="workspace-inline-actions">
            <button class="workspace-link-action" type="button" onclick={openCreateMaterial}>Material hinzufügen</button>
            <button class="workspace-link-action" type="button" onclick={openCreateTask}>Aufgabe hinzufügen</button>
          </div>
        </section>
      {/if}

    {#if !isModuleEditor || moduleSelection.kind === "material" || moduleSelection.kind === "new-material"}
    <TeacherNodeEditorSection
      eyebrow={showCreateMaterial ? "Neues Material" : "Material"}
      title={showCreateMaterial ? "Material anlegen" : "Material bearbeiten"}
      createLabel="Material hinzufügen"
      showCreate={showCreateMaterial}
      hasItems={isModuleEditor ? expandedMaterialId !== null : editorState.materials.length > 0}
      emptyMessage="Noch keine Materialien hinterlegt."
      onCreate={openCreateMaterial}
      workbench={isModuleEditor}
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
          data-draft-target="new-material"
          oninput={captureModuleDraft}
          onchange={captureModuleDraft}
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
            {:else if isModuleEditor && hasDraft("new-material") && !createMaterialSelectedFile}
              <p class="workspace-note">Wähle die Datei nach dem Neuladen erneut aus.</p>
            {/if}
            <label class="workspace-field">
              <span>Alternativtext</span>
              <input name="alt_text" type="text" value={createMaterialValues().alt_text ?? ""} />
            </label>
          {:else}
            <div class="workspace-field">
              <span>Inhalt</span>
              {#if isModuleEditor}
                <MarkdownEditor
                  name="body_md"
                  ariaLabel="Inhalt"
                  value={restoredDraftText("new-material", "body_md", createMaterialValues().body_md ?? "")}
                  placeholder="Material eingeben …"
                  onInput={(value) => captureMarkdownDraft("new-material", "body_md", value)}
                />
              {:else}
                <textarea name="body_md" rows="7">{createMaterialValues().body_md ?? ""}</textarea>
              {/if}
            </div>
          {/if}

          {#if createMaterialClientError}
            <p class="workspace-note workspace-note--error">{createMaterialClientError}</p>
          {/if}

          {#if actionError(form?.createMaterial)}
            <p class="workspace-note workspace-note--error">{actionError(form?.createMaterial)}</p>
          {/if}

          <div class="workspace-node-editor-card-actions">
            {#if isModuleEditor && hasDraft("new-material")}<button class="workspace-link-action workspace-link-action--subtle" type="button" onclick={discardCurrentDraft}>Verwerfen</button>{/if}
            <button class="workspace-link-action" type="submit">Material hinzufügen</button>
          </div>
        </form>
      {/snippet}

      {#snippet list()}
        {#each editorState.materials.filter((material) => !isModuleEditor || expandedMaterialId === material.id) as material}
          <article class:workspace-node-editor-card--expanded={expandedMaterialId === material.id} class:workspace-node-editor-card--workbench={isModuleEditor} class="workspace-node-editor-card workspace-node-editor-entry">
            {#if !isModuleEditor}
              <button class="workspace-node-editor-entry-summary" type="button" onclick={() => toggleMaterial(material.id)}>
              <div class="workspace-node-editor-entry-summary-bar"></div>
              <div class="workspace-node-editor-entry-summary-copy">
                <p class="workspace-node-editor-entry-kicker">{materialKindLabel(material)}</p>
                <h3>{material.title}</h3>
                <p class="workspace-node-editor-entry-meta">{materialMeta(material)}</p>
              </div>
              <span aria-hidden="true" class="workspace-node-editor-entry-toggle">{expandedMaterialId === material.id ? "−" : "+"}</span>
              </button>
            {/if}

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
                        {#if isModuleEditor}
                          <button class="workspace-node-editor-card-menu__danger" type="button" onclick={() => openContentDeleteDialog("material", material.id, material.title)}>Entfernen</button>
                        {:else}
                          <input type="hidden" name="confirmed" value="1" />
                          <button class="workspace-node-editor-card-menu__danger" type="submit">Entfernen</button>
                        {/if}
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

                <form method="POST" action="?/saveMaterial" class="workspace-node-editor-card-form" use:enhance={enhanceEditorForm} data-draft-target={`material:${material.id}`} oninput={captureModuleDraft} onchange={captureModuleDraft}>
                  <input type="hidden" name="section_id" value={sectionId()} />
                  <input type="hidden" name="material_id" value={material.id} />
                  <input type="hidden" name="kind" value={material.kind} />

                  <label class="workspace-field">
                    <span>Titel</span>
                    <input name="title" type="text" value={materialValues(material).title ?? material.title} />
                  </label>

                  {#if material.kind === "markdown"}
                    <div class="workspace-field">
                      <span>Inhalt</span>
                      {#if isModuleEditor}
                        <MarkdownEditor
                          name="body_md"
                          ariaLabel="Inhalt"
                          value={restoredDraftText(`material:${material.id}`, "body_md", materialValues(material).body_md ?? material.body_md ?? "")}
                          placeholder="Material eingeben …"
                          onInput={(value) => captureMarkdownDraft(`material:${material.id}`, "body_md", value)}
                        />
                      {:else}
                        <textarea name="body_md" rows="7">{materialValues(material).body_md ?? material.body_md ?? ""}</textarea>
                      {/if}
                    </div>
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
                    {#if isModuleEditor && hasDraft(`material:${material.id}`)}<button class="workspace-link-action workspace-link-action--subtle" type="button" onclick={discardCurrentDraft}>Verwerfen</button>{/if}
                    <button class="workspace-link-action" type="submit">{isModuleEditor ? "Änderungen speichern" : "Speichern"}</button>
                  </div>
                </form>
              </div>
            {/if}
          </article>
        {/each}
      {/snippet}
    </TeacherNodeEditorSection>
    {/if}

    {#if !isModuleEditor || moduleSelection.kind === "task" || moduleSelection.kind === "new-task"}
    <TeacherNodeEditorSection
      eyebrow={showCreateTask ? "Neue Aufgabe" : "Aufgabe"}
      title={showCreateTask ? "Aufgabe anlegen" : "Aufgabe bearbeiten"}
      createLabel="Aufgabe hinzufügen"
      showCreate={showCreateTask}
      hasItems={isModuleEditor ? expandedTaskId !== null : editorState.tasks.length > 0}
      emptyMessage="Noch keine Aufgaben hinterlegt."
      onCreate={openCreateTask}
      workbench={isModuleEditor}
    >
      {#snippet create()}
        <form method="POST" action="?/createTask" class="workspace-node-editor-card-form" use:enhance={enhanceEditorForm} data-draft-target="new-task" oninput={captureModuleDraft} onchange={captureModuleDraft}>
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
            <div class="workspace-field">
              <span>Anweisung & Beschreibung</span>
              {#if isModuleEditor}
                <MarkdownEditor
                  name="instruction_md"
                  ariaLabel="Anweisung & Beschreibung"
                  value={restoredDraftText("new-task", "instruction_md", createTaskValues().instruction_md ?? "")}
                  placeholder="Aufgabenstellung eingeben …"
                  onInput={(value) => captureMarkdownDraft("new-task", "instruction_md", value)}
                />
              {:else}
                <textarea name="instruction_md" rows="7">{createTaskValues().instruction_md ?? ""}</textarea>
              {/if}
            </div>

            {#if isModuleEditor}
              <TeacherCriteriaEditor initialValues={restoredDraftList("new-task", "criteria[]", createCriteriaItems())} />
            {:else}
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
            {/if}

            {#if createTaskKind === "dialog"}
              <p class="workspace-note">Interne Rolle, Lernziel und Lehrkraft-Kontext werden Lernenden nicht angezeigt.</p>
              <fieldset class="teacher-module-form-group">
                <legend>Dialogpartner</legend>
                <div class="workspace-node-editor-grid">
                  <label class="workspace-field"><span>Name des KI-Partners</span><input name="dialog_partner_name" maxlength="120" value={createTaskValues().dialog_partner_name ?? ""} /></label>
                  <label class="workspace-field"><span>Antwortmodus</span><select name="dialog_response_mode" value={createTaskValues().dialog_response_mode ?? "free_text"}><option value="free_text">Freitext</option><option value="hybrid">Freitext mit Satzanfängen</option></select></label>
                </div>
                <label class="workspace-field"><span>Sichtbare Kurzbeschreibung</span><textarea name="dialog_partner_description_md" rows="3">{createTaskValues().dialog_partner_description_md ?? ""}</textarea></label>
                <label class="workspace-field"><span>Interne Rolleninstruktion</span><textarea name="dialog_role_md" rows="4">{createTaskValues().dialog_role_md ?? ""}</textarea></label>
              </fieldset>
              <fieldset class="teacher-module-form-group">
                <legend>Gesprächsführung</legend>
                <label class="workspace-field"><span>Internes Lernziel</span><textarea name="dialog_learning_goal_md" rows="3">{createTaskValues().dialog_learning_goal_md ?? ""}</textarea></label>
                <label class="workspace-field"><span>Eröffnungsnachricht</span><textarea name="dialog_opening_message_md" rows="3">{createTaskValues().dialog_opening_message_md ?? ""}</textarea></label>
                <label class="workspace-field"><span>Max. Schülerantworten</span><input name="dialog_max_rounds" min="1" max="12" type="number" value={createTaskValues().dialog_max_rounds ?? "8"} /></label>
              </fieldset>
              <fieldset class="teacher-module-form-group">
                <legend>Abschluss</legend>
                <label class="workspace-field"><span>Optionaler Abschlussauftrag</span><textarea name="dialog_closing_prompt_md" rows="3">{createTaskValues().dialog_closing_prompt_md ?? ""}</textarea></label>
              </fieldset>
            {/if}
          {/if}

          <details class="teacher-module-advanced-settings" open={!isModuleEditor}>
            <summary>Weitere Einstellungen</summary>
            <label class="workspace-field"><span>Lehrkraft-Kontext</span><textarea name="teacher_context_md" rows="4">{createTaskValues().teacher_context_md ?? ""}</textarea></label>
            <div class="workspace-node-editor-grid">
              <label class="workspace-field"><span>Fällig bis</span><input name="due_at" type="datetime-local" value={createTaskValues().due_at ?? ""} /></label>
              <label class="workspace-field"><span>Max. Versuche</span><input name="max_attempts" min="1" type="number" value={createTaskValues().max_attempts ?? ""} /></label>
            </div>
          </details>

          <input name="h5p_content_id" type="hidden" value={createTaskValues().h5p_content_id ?? ""} />

          {#if actionError(form?.createTask)}
            <p class="workspace-note workspace-note--error">{actionError(form?.createTask)}</p>
          {/if}

          <div class="workspace-node-editor-card-actions">
            {#if isModuleEditor && hasDraft("new-task")}<button class="workspace-link-action workspace-link-action--subtle" type="button" onclick={discardCurrentDraft}>Verwerfen</button>{/if}
            <button class="workspace-link-action" type="submit">Aufgabe hinzufügen</button>
          </div>
        </form>
      {/snippet}

      {#snippet list()}
        {#each editorState.tasks.filter((task) => !isModuleEditor || expandedTaskId === task.id) as task, index}
          <article class:workspace-node-editor-card--expanded={expandedTaskId === task.id} class:workspace-node-editor-card--workbench={isModuleEditor} class="workspace-node-editor-card workspace-node-editor-entry workspace-node-editor-entry--task">
            {#if !isModuleEditor}
              <button class="workspace-node-editor-entry-summary" type="button" onclick={() => toggleTask(task.id)}>
              <div class="workspace-node-editor-entry-summary-bar"></div>
              <div class="workspace-node-editor-entry-summary-copy">
                <p class="workspace-node-editor-entry-kicker">{taskKindLabel(task)}</p>
                <h3>{taskTitle(task, index)}</h3>
                <p class="workspace-node-editor-entry-meta">{taskMeta(task)}</p>
              </div>
              <span aria-hidden="true" class="workspace-node-editor-entry-toggle">{expandedTaskId === task.id ? "−" : "+"}</span>
              </button>
            {/if}

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
                        {#if isModuleEditor}
                          <button class="workspace-node-editor-card-menu__danger" type="button" onclick={() => openContentDeleteDialog("task", task.id, taskTitle(task, index))}>Entfernen</button>
                        {:else}
                          <input type="hidden" name="confirmed" value="1" />
                          <button class="workspace-node-editor-card-menu__danger" type="submit">Entfernen</button>
                        {/if}
                      </form>
                    </div>
                  </details>
                </div>

                <form method="POST" action="?/saveTask" class="workspace-node-editor-card-form" use:enhance={enhanceEditorForm} data-draft-target={`task:${task.id}`} oninput={captureModuleDraft} onchange={captureModuleDraft}>
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
                    <div class="workspace-field">
                      <span>Anweisung & Beschreibung</span>
                      {#if isModuleEditor}
                        <MarkdownEditor
                          name="instruction_md"
                          ariaLabel="Anweisung & Beschreibung"
                          value={restoredDraftText(`task:${task.id}`, "instruction_md", taskInstructionValue(task))}
                          placeholder="Aufgabenstellung eingeben …"
                          onInput={(value) => captureMarkdownDraft(`task:${task.id}`, "instruction_md", value)}
                        />
                      {:else}
                        <textarea name="instruction_md" rows="7">{taskInstructionValue(task)}</textarea>
                      {/if}
                    </div>

                    {#if isModuleEditor}
                      <TeacherCriteriaEditor initialValues={restoredDraftList(`task:${task.id}`, "criteria[]", taskCriteriaItems(task))} />
                    {:else}
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
                    {/if}

                    {#if task.kind === "dialog"}
                      <p class="workspace-note">Interne Rolle, Lernziel und Lehrkraft-Kontext werden Lernenden nicht angezeigt. Die Vorschau nutzt die zuletzt gespeicherte Fassung.</p>
                      <fieldset class="teacher-module-form-group">
                        <legend>Dialogpartner</legend>
                        <div class="workspace-node-editor-grid">
                          <label class="workspace-field"><span>Name des KI-Partners</span><input name="dialog_partner_name" maxlength="120" value={taskValues(task).dialog_partner_name ?? task.dialog?.partner_name ?? ""} /></label>
                          <label class="workspace-field"><span>Antwortmodus</span><select name="dialog_response_mode" value={taskValues(task).dialog_response_mode ?? task.dialog?.response_mode ?? "free_text"}><option value="free_text">Freitext</option><option value="hybrid">Freitext mit Satzanfängen</option></select></label>
                        </div>
                        <label class="workspace-field"><span>Sichtbare Kurzbeschreibung</span><textarea name="dialog_partner_description_md" rows="3">{taskValues(task).dialog_partner_description_md ?? task.dialog?.partner_description_md ?? ""}</textarea></label>
                        <label class="workspace-field"><span>Interne Rolleninstruktion</span><textarea name="dialog_role_md" rows="4">{taskValues(task).dialog_role_md ?? task.dialog?.role_md ?? ""}</textarea></label>
                      </fieldset>
                      <fieldset class="teacher-module-form-group">
                        <legend>Gesprächsführung</legend>
                        <label class="workspace-field"><span>Internes Lernziel</span><textarea name="dialog_learning_goal_md" rows="3">{taskValues(task).dialog_learning_goal_md ?? task.dialog?.learning_goal_md ?? ""}</textarea></label>
                        <label class="workspace-field"><span>Eröffnungsnachricht</span><textarea name="dialog_opening_message_md" rows="3">{taskValues(task).dialog_opening_message_md ?? task.dialog?.opening_message_md ?? ""}</textarea></label>
                        <label class="workspace-field"><span>Max. Schülerantworten</span><input name="dialog_max_rounds" min="1" max="12" type="number" value={taskValues(task).dialog_max_rounds ?? String(task.dialog?.max_rounds ?? 8)} /></label>
                      </fieldset>
                      <fieldset class="teacher-module-form-group">
                        <legend>Abschluss</legend>
                        <label class="workspace-field"><span>Optionaler Abschlussauftrag</span><textarea name="dialog_closing_prompt_md" rows="3">{taskValues(task).dialog_closing_prompt_md ?? task.dialog?.closing_prompt_md ?? ""}</textarea></label>
                      </fieldset>
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

                  <details class="teacher-module-advanced-settings" open={!isModuleEditor}>
                    <summary>Weitere Einstellungen</summary>
                    <label class="workspace-field"><span>Lehrkraft-Kontext</span><textarea name="teacher_context_md" rows="4">{taskTeacherContextValue(task)}</textarea></label>
                    <div class="workspace-node-editor-grid">
                      <label class="workspace-field"><span>Fällig bis</span><input name="due_at" type="datetime-local" value={taskDueAtValue(task)} /></label>
                      <label class="workspace-field"><span>Max. Versuche</span><input name="max_attempts" type="number" min="1" value={taskMaxAttemptsValue(task)} /></label>
                    </div>
                  </details>

                  {#if taskError(task)}
                    <p class="workspace-note workspace-note--error">{taskError(task)}</p>
                  {/if}

                  <div class="workspace-node-editor-card-actions">
                    {#if isModuleEditor && hasDraft(`task:${task.id}`)}<button class="workspace-link-action workspace-link-action--subtle" type="button" onclick={discardCurrentDraft}>Verwerfen</button>{/if}
                    <button class="workspace-link-action" type="submit">{isModuleEditor ? "Änderungen speichern" : "Speichern"}</button>
                  </div>
                </form>
              </div>
            {/if}
          </article>
        {/each}
      {/snippet}
    </TeacherNodeEditorSection>
    {/if}
    </div>
  </section>
</div>

{#if deleteModuleOpen && data.moduleDeletionImpact}
  <GraphDeleteDialog
    impact={data.moduleDeletionImpact}
    action="?/deleteModule"
    error={actionError(form?.deleteModule)}
    onCancel={closeDeleteModuleDialog}
    enhanceForm={enhanceEditorForm}
  />
{/if}

{#if deleteContentTarget}
  <ContentDeleteDialog
    kind={deleteContentTarget.kind}
    id={deleteContentTarget.id}
    title={deleteContentTarget.title}
    sectionId={sectionId()}
    error={deleteContentTarget.kind === "material" ? actionError(form?.deleteMaterial) : actionError(form?.deleteTask)}
    onCancel={closeContentDeleteDialog}
    enhanceForm={enhanceEditorForm}
  />
{/if}
