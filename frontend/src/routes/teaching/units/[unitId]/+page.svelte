<script lang="ts">
  import { applyAction, enhance } from "$app/forms";
  import { invalidateAll, replaceState } from "$app/navigation";
  import { page } from "$app/state";
  import {
    Controls,
    Panel,
    SvelteFlow,
    type Connection
  } from "@xyflow/svelte";
  import "@xyflow/svelte/dist/style.css";
  import type { SubmitFunction } from "@sveltejs/kit";

  import GraphPhaseBand from "$lib/components/teacher-unit-graph/GraphPhaseBand.svelte";
  import type { TeacherGraphCommandBarAction } from "$lib/components/teacher-unit-graph/TeacherGraphCommandBar.svelte";
  import TeacherGraphEdge from "$lib/components/teacher-unit-graph/TeacherGraphEdge.svelte";
  import GraphUnitNode from "$lib/components/teacher-unit-graph/GraphUnitNode.svelte";
  import GraphInspectorPanel from "$lib/components/ui/GraphInspectorPanel.svelte";
  import TeacherGraphWorkspaceFrame from "$lib/components/ui/TeacherGraphWorkspaceFrame.svelte";
  import {
    buildTeacherUnitFlow,
    type TeacherFlowEdge,
    type TeacherFlowEdgeData,
    type TeacherFlowNode,
    type TeacherFlowNodeData
  } from "$lib/graph/teacher-unit-flow";
  import type {
    TeacherUnitWorkspaceView,
    TeacherUnitWorkspaceEdgeSelection,
    TeacherUnitWorkspaceGraphPhase,
    TeacherUnitWorkspaceModuleItem,
    TeacherUnitWorkspaceSectionItem,
    TeacherUnitWorkspaceSelection
  } from "$lib/types/home";
  import type { ActionData, PageData } from "./$types";

  let { data, form }: { data: PageData; form: ActionData } = $props();

  function plainWorkspace(workspace: TeacherUnitWorkspaceView): TeacherUnitWorkspaceView {
    return JSON.parse(JSON.stringify(workspace)) as TeacherUnitWorkspaceView;
  }

  function initialWorkspace(): TeacherUnitWorkspaceView {
    return plainWorkspace(data.workspace);
  }

  function workspaceGraphSignature(workspace: TeacherUnitWorkspaceView): string {
    if (workspace.graph.kind === "linear") {
      return JSON.stringify({
        unit: workspace.unit.id,
        kind: workspace.graph.kind,
        sections: (workspace.graph.nodes ?? []).map((section) => [section.id, section.title, section.position]),
        edges: workspace.graph.edges
      });
    }

    return JSON.stringify({
      unit: workspace.unit.id,
      kind: workspace.graph.kind,
      phases: (workspace.graph.phases ?? []).map((phase) => [
        phase.id,
        phase.title,
        phase.position,
        phase.modules.map((module) => [
          module.id,
          module.title,
          module.phase_id,
          module.position_in_phase,
          module.required_prereq_count
        ])
      ]),
      edges: workspace.graph.edges
    });
  }

  let flowNodes = $state.raw<TeacherFlowNode[]>([]);
  let flowEdges = $state.raw<TeacherFlowEdge[]>([]);
  let flowBusy = $state(false);
  let graphMessage = $state<{ tone: "info" | "success" | "error"; text: string } | null>(null);
  let workspaceState = $state<TeacherUnitWorkspaceView>(initialWorkspace());
  let localSelection = $state<TeacherUnitWorkspaceSelection>({ kind: "none" });
  let openModulePropertiesId = $state<string | null>(null);
  let handledForm: ActionData | undefined = undefined;
  let initialCreateDialogStateApplied = $state(false);
  let createPhaseOpen = $state(false);
  let createModuleOpen = $state(false);
  let createSectionOpen = $state(false);
  let flowViewport = $state<{ x: number; y: number; zoom: number } | undefined>(undefined);
  let lastWorkspaceSignature = "";
  let pendingViewportReset = false;
  let flowBuildSequence = 0;

  const nodeTypes = {
    unitNode: GraphUnitNode,
    phaseBand: GraphPhaseBand
  };

  const edgeTypes = {
    teacherEdge: TeacherGraphEdge
  };

  const enhanceGraphForm: SubmitFunction = () => {
    return async ({ result, update }) => {
      const success = graphActionSuccessFromResult(result);
      if (success?.next) {
        syncUrlPatch(success.next);
      }
      if (success) {
        closeCreateDialogsFromNext(success.next);
        await applyAction(result);
        await invalidateAll();
        return;
      }
      await update({ reset: false });
    };
  };

  type GraphActionSuccess = {
    ok: true;
    message: string;
    next?: Record<string, string | null>;
  };

  function asGraphActionSuccess(value: unknown): GraphActionSuccess | null {
    if (!value || typeof value !== "object") {
      return null;
    }
    const candidate = value as Partial<GraphActionSuccess>;
    return candidate.ok ? (candidate as GraphActionSuccess) : null;
  }

  function graphActionSuccessFromResult(result: unknown): GraphActionSuccess | null {
    if (!result || typeof result !== "object") {
      return null;
    }

    const data = (result as { data?: unknown }).data;
    if (!data || typeof data !== "object") {
      return null;
    }

    for (const value of Object.values(data)) {
      const success = asGraphActionSuccess(value);
      if (success) {
        return success;
      }
    }
    return null;
  }

  function actionError(value: unknown): string | null {
    if (!value || typeof value !== "object") {
      return null;
    }
    const candidate = value as { error?: string };
    return candidate.error ?? null;
  }

  function actionValues<T extends Record<string, string>>(value: unknown): Partial<T> {
    if (!value || typeof value !== "object") {
      return {};
    }
    const candidate = value as { values?: Partial<T> };
    return candidate.values ?? {};
  }

  function createPhaseValues() {
    return actionValues<{ title: string }>(form?.createPhase);
  }

  function createModuleValues() {
    return actionValues<{ title: string; phase_id: string }>(form?.createModule);
  }

  function createSectionValues() {
    return actionValues<{ title: string }>(form?.createSection);
  }

  function currentUrl(): URL {
    return new URL(page.url);
  }

  function pageHref(next: Record<string, string | null>): string {
    const baseUrl = currentUrl();
    const params = new URLSearchParams(baseUrl.searchParams);
    for (const [key, value] of Object.entries(next)) {
      if (!value) {
        params.delete(key);
      } else {
        params.set(key, value);
      }
    }
    const query = params.toString();
    return query ? `${baseUrl.pathname}?${query}` : baseUrl.pathname;
  }

  function quickEditOpen(): boolean {
    return currentUrl().searchParams.get("quick") === "1";
  }

  function showCreatePhaseDialog(): boolean {
    return createPhaseOpen || (!initialCreateDialogStateApplied && Boolean(data.showCreatePhaseDialog || form?.createPhase));
  }

  function showCreateModuleDialog(): boolean {
    return createModuleOpen || (!initialCreateDialogStateApplied && Boolean(data.showCreateModuleDialog || form?.createModule));
  }

  function showCreateSectionDialog(): boolean {
    return createSectionOpen || (!initialCreateDialogStateApplied && Boolean(data.showCreateSectionDialog || form?.createSection));
  }

  function selectedPhaseId(): string | null {
    if (localSelection.kind === "phase") {
      return localSelection.phase.id;
    }
    if (localSelection.kind === "module") {
      return localSelection.module.phase_id;
    }
    return currentUrl().searchParams.get("phase");
  }

  function flowNodeData(node: TeacherFlowNode): TeacherFlowNodeData {
    return node.data as TeacherFlowNodeData;
  }

  function flowEdgeData(edge: TeacherFlowEdge): TeacherFlowEdgeData {
    return (edge.data as TeacherFlowEdgeData | undefined) ?? { from: edge.source, to: edge.target };
  }

  function openModuleProperties(moduleId: string) {
    openModulePropertiesId = moduleId;
  }

  function closeModuleProperties() {
    openModulePropertiesId = null;
  }

  function openCreatePhaseDialog() {
    createPhaseOpen = true;
  }

  function closeCreatePhaseDialog() {
    createPhaseOpen = false;
    if (currentUrl().searchParams.has("create-phase")) {
      replaceCurrentUrl(pageHref({ "create-phase": null }));
    }
  }

  function openCreateModuleDialog() {
    createModuleOpen = true;
  }

  function closeCreateModuleDialog() {
    createModuleOpen = false;
    if (currentUrl().searchParams.has("create-module")) {
      replaceCurrentUrl(pageHref({ "create-module": null }));
    }
  }

  function openCreateSectionDialog() {
    createSectionOpen = true;
  }

  function closeCreateSectionDialog() {
    createSectionOpen = false;
    if (currentUrl().searchParams.has("create-section")) {
      replaceCurrentUrl(pageHref({ "create-section": null }));
    }
  }

  function closeCreateDialogsFromNext(next: Record<string, string | null> | undefined) {
    if (next?.["create-phase"] === null) {
      createPhaseOpen = false;
    }
    if (next?.["create-module"] === null) {
      createModuleOpen = false;
    }
    if (next?.["create-section"] === null) {
      createSectionOpen = false;
    }
  }

  function replaceCurrentUrl(href: string) {
    if (typeof window !== "undefined") {
      replaceState(href, page.state);
    }
  }

  function graphCommandActions(): TeacherGraphCommandBarAction[] {
    if (workspaceState.graph.kind === "linear") {
      return [{ label: "Abschnitt hinzufügen", active: showCreateSectionDialog(), onClick: openCreateSectionDialog }];
    }

    return [
      {
        label: "Phase hinzufügen",
        active: showCreatePhaseDialog(),
        onClick: openCreatePhaseDialog
      },
      {
        label: "Modul hinzufügen",
        active: showCreateModuleDialog(),
        onClick: openCreateModuleDialog
      }
    ];
  }

  function isInteractiveTarget(target: EventTarget | null): boolean {
    return target instanceof Element && Boolean(target.closest("a,button,summary,input,textarea,select,label,form"));
  }

  function modularPhases(workspace: TeacherUnitWorkspaceView = workspaceState) {
    return workspace.graph.kind === "modular" ? (workspace.graph.phases ?? []) : [];
  }

  function graphSections(): TeacherUnitWorkspaceSectionItem[] {
    return workspaceState.graph.kind === "linear" ? (workspaceState.graph.nodes ?? []) : [];
  }

  function allModules(): TeacherUnitWorkspaceModuleItem[] {
    return modularPhases().flatMap((phase) => phase.modules);
  }

  function findPhaseById(phaseId: string): TeacherUnitWorkspaceGraphPhase | null {
    return modularPhases().find((phase) => phase.id === phaseId) ?? null;
  }

  function findModuleById(moduleId: string): TeacherUnitWorkspaceModuleItem | null {
    return allModules().find((module) => module.id === moduleId) ?? null;
  }

  function findSectionById(sectionId: string): TeacherUnitWorkspaceSectionItem | null {
    return graphSections().find((section) => section.id === sectionId) ?? null;
  }

  function edgeExists(fromId: string, toId: string): boolean {
    return (workspaceState.graph.edges ?? []).some((edge) => edge.from === fromId && edge.to === toId);
  }

  function deriveSectionSelection(sectionId: string): TeacherUnitWorkspaceSelection {
    const section = findSectionById(sectionId);
    if (!section) {
      return { kind: "none" };
    }
    return {
      kind: "section",
      section: {
        id: section.id,
        title: section.title,
        position: section.position,
        editor_href: section.editor_href
      }
    };
  }

  function derivePhaseSelection(phaseId: string): TeacherUnitWorkspaceSelection {
    const phase = findPhaseById(phaseId);
    if (!phase) {
      return { kind: "none" };
    }
    return {
      kind: "phase",
      phase: {
        id: phase.id,
        title: phase.title,
        position: phase.position
      }
    };
  }

  function deriveModuleSelection(moduleId: string): TeacherUnitWorkspaceSelection {
    const module = findModuleById(moduleId);
    if (!module) {
      return { kind: "none" };
    }
    return {
      kind: "module",
      module: {
        id: module.id,
        title: module.title,
        phase_id: module.phase_id,
        position_in_phase: module.position_in_phase,
        required_prereq_count: module.required_prereq_count,
        materials_count: module.materials_count,
        tasks_count: module.tasks_count,
        editor_href: module.editor_href
      }
    };
  }

  function deriveEdgeSelection(fromId: string, toId: string): TeacherUnitWorkspaceSelection {
    const fromModule = findModuleById(fromId);
    const toModule = findModuleById(toId);
    if (!fromModule || !toModule) {
      return { kind: "none" };
    }

    const edge: TeacherUnitWorkspaceEdgeSelection = {
      from_id: fromModule.id,
      to_id: toModule.id,
      from_title: fromModule.title,
      to_title: toModule.title,
      exists: edgeExists(fromId, toId)
    };
    return { kind: "edge", edge };
  }

  function syncSelectionUrl(selection: TeacherUnitWorkspaceSelection) {
    if (typeof window === "undefined") {
      return;
    }

    const url = currentUrl();
    ["section", "phase", "module", "edgeFrom", "edgeTo"].forEach((key) => url.searchParams.delete(key));

    if (selection.kind === "section") {
      url.searchParams.set("section", selection.section.id);
    } else if (selection.kind === "phase") {
      url.searchParams.set("phase", selection.phase.id);
    } else if (selection.kind === "module") {
      url.searchParams.set("module", selection.module.id);
    } else if (selection.kind === "edge") {
      url.searchParams.set("edgeFrom", selection.edge.from_id);
      url.searchParams.set("edgeTo", selection.edge.to_id);
    }

    replaceCurrentUrl(`${url.pathname}${url.search}${url.hash}`);
  }

  function syncUrlPatch(next: Record<string, string | null>) {
    if (typeof window === "undefined") {
      return;
    }

    replaceCurrentUrl(pageHref(next));
  }

  async function applyLocalSelection(selection: TeacherUnitWorkspaceSelection) {
    localSelection = selection;
    syncSelectionUrl(selection);
  }

  function setGraphMessage(text: string, tone: "info" | "success" | "error" = "info") {
    graphMessage = { text, tone };
  }

  async function apiJson(method: string, href: string, body?: unknown): Promise<unknown> {
    const response = await fetch(href, {
      method,
      credentials: "same-origin",
      headers: body ? { "content-type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined
    });

    if (!response.ok) {
      let errorPayload: { detail?: string; error?: string } = {};
      try {
        errorPayload = await response.json();
      } catch {
        errorPayload = {};
      }
      throw new Error(errorPayload.detail || errorPayload.error || "request_failed");
    }

    if (response.status === 204) {
      return null;
    }
    return response.json();
  }

  async function reloadWorkspace(next: Record<string, string | null> = {}) {
    syncUrlPatch(next);
    await invalidateAll();
  }

  async function rebuildFlow(
    selection: TeacherUnitWorkspaceSelection = localSelection,
    workspaceForBuild: TeacherUnitWorkspaceView = workspaceState
  ) {
    const buildSequence = ++flowBuildSequence;
    flowBusy = true;
    try {
      const saveModuleValues = actionValues<{ title: string; phase_id: string; required_prereq_count: string }>(form?.saveModule);
      const saveModuleFormError = actionError(form?.saveModule);
      const layout = await buildTeacherUnitFlow(workspaceForBuild, selection);
      if (buildSequence !== flowBuildSequence) {
        return;
      }
      flowNodes = layout.nodes.map((node) => {
        const nodeData = flowNodeData(node);
        if (nodeData.kind !== "module") {
          return node;
        }

        const showsQuickEdit = openModulePropertiesId === node.id && selection.kind === "module" && selection.module.id === node.id;

        if (!showsQuickEdit) {
          return {
            ...node,
            data: {
              ...nodeData,
              enhanceGraphForm,
              onOpenProperties: () => openModuleProperties(node.id),
              onCloseProperties: null,
              quickEdit: null
            }
          };
        }

        return {
          ...node,
          data: {
            ...nodeData,
            enhanceGraphForm,
            onOpenProperties: null,
            onCloseProperties: () => closeModuleProperties(),
            quickEdit: {
              title: saveModuleValues.title ?? selection.module.title,
              phaseId: saveModuleValues.phase_id ?? selection.module.phase_id,
              phaseOptions: modularPhases(workspaceForBuild).map((phase) => ({ id: phase.id, title: phase.title })),
              requiredPrereqCount:
                saveModuleValues.required_prereq_count ?? String(selection.module.required_prereq_count),
              error: saveModuleFormError
            }
          }
        };
      });
      flowEdges = layout.edges.map((edge) => ({
        ...edge,
        data: {
          ...flowEdgeData(edge),
          enhanceGraphForm
        }
      }));
      if (pendingViewportReset) {
        flowViewport = { x: 0, y: 0, zoom: 1 };
        pendingViewportReset = false;
      }
    } finally {
      if (buildSequence === flowBuildSequence) {
        flowBusy = false;
      }
    }
  }

  function scheduleFlowRebuild(
    selection: TeacherUnitWorkspaceSelection = localSelection,
    workspaceForBuild: TeacherUnitWorkspaceView = workspaceState
  ) {
    queueMicrotask(() => {
      void rebuildFlow(selection, workspaceForBuild);
    });
  }

  $effect(() => {
    if (initialCreateDialogStateApplied) {
      return;
    }
    initialCreateDialogStateApplied = true;
    createPhaseOpen = Boolean(data.showCreatePhaseDialog);
    createModuleOpen = Boolean(data.showCreateModuleDialog || form?.createModule);
    createSectionOpen = Boolean(data.showCreateSectionDialog);
  });

  $effect(() => {
    const nextWorkspaceSignature = workspaceGraphSignature(data.workspace);
    const workspaceChanged = Boolean(lastWorkspaceSignature && nextWorkspaceSignature !== lastWorkspaceSignature);
    if (workspaceChanged) {
      pendingViewportReset = true;
    }
    lastWorkspaceSignature = nextWorkspaceSignature;
    const nextWorkspace = plainWorkspace(data.workspace);
    workspaceState = nextWorkspace;
    localSelection = data.workspace.selection;
    openModulePropertiesId = null;
  });

  $effect(() => {
    workspaceState;
    localSelection;
    openModulePropertiesId;
    form?.saveModule;
    const selection = localSelection;
    scheduleFlowRebuild(selection);
  });

  $effect(() => {
    if (!form || form === handledForm) {
      return;
    }

    handledForm = form;

    const saveSectionSuccess = asGraphActionSuccess(form.saveSection);
    const createSectionSuccess = asGraphActionSuccess(form.createSection);
    const deleteSectionSuccess = asGraphActionSuccess(form.deleteSection);
    const savePhaseSuccess = asGraphActionSuccess(form.savePhase);
    const createPhaseSuccess = asGraphActionSuccess(form.createPhase);
    const deletePhaseSuccess = asGraphActionSuccess(form.deletePhase);
    const saveModuleSuccess = asGraphActionSuccess(form.saveModule);
    const createModuleSuccess = asGraphActionSuccess(form.createModule);
    const deleteModuleSuccess = asGraphActionSuccess(form.deleteModule);
    const createEdgeSuccess = asGraphActionSuccess(form.createEdge);
    const deleteEdgeSuccess = asGraphActionSuccess(form.deleteEdge);

    if (actionError(form.createPhase)) {
      createPhaseOpen = true;
    }
    if (actionError(form.createModule)) {
      createModuleOpen = true;
    }
    if (actionError(form.createSection)) {
      createSectionOpen = true;
    }

    const success =
      saveSectionSuccess
      ?? createSectionSuccess
      ?? deleteSectionSuccess
      ?? savePhaseSuccess
      ?? createPhaseSuccess
      ?? deletePhaseSuccess
      ?? saveModuleSuccess
      ?? createModuleSuccess
      ?? deleteModuleSuccess
      ?? createEdgeSuccess
      ?? deleteEdgeSuccess;

    if (success) {
      if (success.message) {
        setGraphMessage(success.message, "success");
      }
      if (saveModuleSuccess) {
        openModulePropertiesId =
          typeof saveModuleSuccess.next?.module === "string" ? saveModuleSuccess.next.module : openModulePropertiesId;
      } else if (deleteModuleSuccess || createModuleSuccess || createEdgeSuccess || deleteEdgeSuccess) {
        openModulePropertiesId = null;
      }
      if (createPhaseSuccess) {
        closeCreatePhaseDialog();
      }
      if (createModuleSuccess) {
        closeCreateModuleDialog();
      }
      if (createSectionSuccess) {
        closeCreateSectionDialog();
      }
    }
  });

  function orderedSectionIds(): string[] {
    return flowNodes
      .filter((node) => flowNodeData(node).kind === "section")
      .sort((left, right) => left.position.y - right.position.y)
      .map((node) => node.id);
  }

  async function persistSectionReorder() {
    if (workspaceState.graph.kind !== "linear") {
      return;
    }

    const current = (workspaceState.graph.nodes ?? []).map((node) => node.id);
    const next = orderedSectionIds();

    if (JSON.stringify(current) === JSON.stringify(next)) {
      return;
    }

    try {
      await apiJson("POST", `/teaching/units/${workspaceState.unit.id}/graph/sections`, { section_ids: next });
      setGraphMessage("Abschnitte gespeichert.", "success");
      await reloadWorkspace({ section: localSelection.kind === "section" ? localSelection.section.id : null });
    } catch (error) {
      setGraphMessage("Abschnitte konnten nicht neu geordnet werden.", "error");
      await rebuildFlow(localSelection);
    }
  }

  function moduleNodes(): TeacherFlowNode[] {
    return flowNodes.filter((node) => flowNodeData(node).kind === "module");
  }

  function compareNodeTopLeft(left: TeacherFlowNode, right: TeacherFlowNode): number {
    const byY = left.position.y - right.position.y;
    if (Math.abs(byY) > 12) {
      return byY;
    }
    return left.position.x - right.position.x;
  }

  function sameIds(left: string[], right: string[]): boolean {
    return left.length === right.length && left.every((value, index) => value === right[index]);
  }

  function phaseReorderMessage(detail: string): string {
    switch (detail) {
      case "edge_constraint_violation":
        return "Phasen können wegen bestehender Abhängigkeiten nicht so verschoben werden.";
      case "phase_mismatch":
        return "Die Phasenreihenfolge ist unvollständig. Bitte erneut versuchen.";
      case "phase_not_in_unit":
        return "Mindestens eine Phase gehört nicht zu dieser Lerneinheit.";
      case "invalid_phase_ids":
        return "Die Phasenreihenfolge enthält ungültige Einträge.";
      case "duplicate_phase_ids":
        return "Eine Phase wurde doppelt übermittelt.";
      case "empty_phase_ids":
        return "Es wurde keine Phasenreihenfolge übermittelt.";
      case "invalid_unit_type":
        return "Phasen können nur in modularen Lerneinheiten sortiert werden.";
      default:
        return detail ? `Phasen konnten nicht neu geordnet werden (${detail}).` : "Phasen konnten nicht neu geordnet werden.";
    }
  }

  function moduleReorderMessage(detail: string): string {
    switch (detail) {
      case "edge_constraint_violation":
        return "Verschieben blockiert: Abhängigkeiten zuerst entfernen.";
      case "invalid_module_ids":
        return "Die Modulreihenfolge enthält ungültige Einträge.";
      case "duplicate_module_ids":
        return "Ein Modul wurde doppelt übermittelt.";
      case "empty_module_ids":
        return "Es wurde keine Modulreihenfolge übermittelt.";
      case "phase_not_found":
        return "Die Zielphase wurde nicht gefunden.";
      case "module_not_in_unit":
        return "Mindestens ein Modul gehört nicht zu dieser Lerneinheit.";
      case "invalid_unit_type":
        return "Module können nur in modularen Lerneinheiten sortiert werden.";
      default:
        return detail ? `Module konnten nicht neu geordnet werden (${detail}).` : "Module konnten nicht neu geordnet werden.";
    }
  }

  async function persistModuleReorder(nodeId: string) {
    if (workspaceState.graph.kind !== "modular") {
      return;
    }

    const movedNode = moduleNodes().find((node) => node.id === nodeId);
    if (!movedNode) {
      return;
    }

    const targetPhaseId = flowNodeData(movedNode).phaseId ?? null;
    if (!targetPhaseId) {
      await rebuildFlow(localSelection);
      return;
    }

    const nextIds = moduleNodes()
      .filter((node) => {
        const nodeData = flowNodeData(node);
        return nodeData.phaseId === targetPhaseId;
      })
      .sort(compareNodeTopLeft)
      .map((node) => node.id);

    const currentIds =
      modularPhases()
        .find((phase) => phase.id === targetPhaseId)
        ?.modules.map((module) => module.id) ?? [];

    if (!nextIds.length) {
      console.warn("Module reorder aborted: empty target payload", { nodeId, targetPhaseId });
      await rebuildFlow(localSelection);
      return;
    }

    if (sameIds(currentIds, nextIds)) {
      await rebuildFlow(localSelection);
      return;
    }

    try {
      await apiJson(
        "POST",
        `/teaching/units/${workspaceState.unit.id}/graph/modules`,
        { phase_id: targetPhaseId, module_ids: nextIds }
      );
      setGraphMessage("Module gespeichert.", "success");
      await reloadWorkspace({ module: nodeId, phase: targetPhaseId });
    } catch (error) {
      const detail = error instanceof Error ? error.message : "";
      console.warn("Module reorder failed", {
        detail,
        nodeId,
        targetPhaseId,
        currentIds,
        nextIds
      });
      setGraphMessage(moduleReorderMessage(detail), "error");
      await rebuildFlow(localSelection);
    }
  }

  async function moveSelectedPhase(direction: -1 | 1) {
    if (workspaceState.graph.kind !== "modular" || localSelection.kind !== "phase") {
      return;
    }

    const ids = modularPhases().map((phase) => phase.id);
    const currentIndex = ids.indexOf(localSelection.phase.id);
    const nextIndex = currentIndex + direction;

    if (currentIndex === -1 || nextIndex < 0 || nextIndex >= ids.length) {
      return;
    }

    const reordered = ids.slice();
    const [selected] = reordered.splice(currentIndex, 1);
    reordered.splice(nextIndex, 0, selected);

    try {
      await apiJson("POST", `/teaching/units/${workspaceState.unit.id}/graph/phases`, {
        phase_ids: reordered
      });
      setGraphMessage("Phasen gespeichert.", "success");
      await reloadWorkspace({ phase: localSelection.phase.id });
    } catch (error) {
      const detail = error instanceof Error ? error.message : "";
      setGraphMessage(phaseReorderMessage(detail), "error");
      await rebuildFlow(localSelection);
    }
  }

  async function handleNodeClick({ node, event }: { node: TeacherFlowNode; event: MouseEvent | TouchEvent }) {
    if (isInteractiveTarget(event.target)) {
      return;
    }

    const nodeData = flowNodeData(node);
    if (nodeData.kind === "section") {
      closeModuleProperties();
      await applyLocalSelection(deriveSectionSelection(node.id));
      return;
    }
    if (nodeData.kind === "phase") {
      const phaseId = nodeData.phaseId ?? node.id.replace(/^phase:/, "");
      closeModuleProperties();
      await applyLocalSelection(derivePhaseSelection(phaseId));
      return;
    }
    if (nodeData.kind === "module") {
      if (openModulePropertiesId && openModulePropertiesId !== node.id) {
        closeModuleProperties();
      }
      await applyLocalSelection(deriveModuleSelection(node.id));
    }
  }

  async function handleEdgeClick({ edge, event }: { edge: TeacherFlowEdge; event: MouseEvent }) {
    if (isInteractiveTarget(event.target)) {
      return;
    }

    const edgeData = flowEdgeData(edge);
    closeModuleProperties();
    await applyLocalSelection(deriveEdgeSelection(edgeData.from, edgeData.to));
  }

  async function handlePaneClick() {
    closeModuleProperties();
    await applyLocalSelection({ kind: "none" });
  }

  async function handleConnect(connection: Connection) {
    if (workspaceState.graph.kind !== "modular" || !connection.source || !connection.target || connection.source === connection.target) {
      return;
    }

    try {
      await apiJson("POST", `/teaching/units/${workspaceState.unit.id}/graph/edges`, {
        from_module_id: connection.source,
        to_module_id: connection.target
      });
      setGraphMessage("Kante angelegt.", "success");
      await reloadWorkspace({
        module: connection.target,
        edgeFrom: connection.source,
        edgeTo: connection.target
      });
    } catch (error) {
      setGraphMessage("Die Kante konnte nicht angelegt werden.", "error");
      await rebuildFlow(localSelection);
    }
  }

  async function handleNodeDragStop({
    targetNode,
    nodes
  }: {
    targetNode: TeacherFlowNode | null;
    nodes: TeacherFlowNode[];
  }) {
    const node = targetNode ?? nodes[0];
    if (!node) {
      return;
    }

    const nodeData = flowNodeData(node);
    if (nodeData.kind === "section") {
      await persistSectionReorder();
      return;
    }

    if (nodeData.kind === "module") {
      await persistModuleReorder(node.id);
    }
  }
</script>

<svelte:head>
  <title>{workspaceState.unit.title} | GUSTAV</title>
</svelte:head>

{#snippet unitHeaderActions()}
  <a class="workspace-link-action workspace-link-action--subtle" href={workspaceState.unit.edit_href}>Bearbeiten</a>
  <a class="workspace-link-action workspace-link-action--danger" href={pageHref({ delete: "1" })}>Löschen</a>
{/snippet}

{#snippet unitCommandPopovers()}
  {#if showCreatePhaseDialog()}
    <div class="workspace-unit-commandbar-popover" role="dialog" aria-label="Phase hinzufügen">
      <div class="workspace-unit-commandbar-popover__header">
        <div>
          <p class="workspace-label">Canvas</p>
          <h2>Phase hinzufügen</h2>
        </div>
        <button class="workspace-link-action workspace-link-action--subtle" type="button" onclick={closeCreatePhaseDialog}>
          Schließen
        </button>
      </div>
      <form method="POST" action="?/createPhase" class="workspace-form workspace-form--compact" use:enhance={enhanceGraphForm}>
        <label class="workspace-field">
          <span>Titel</span>
          <input name="title" type="text" value={createPhaseValues().title ?? ""} />
        </label>
        {#if actionError(form?.createPhase)}
          <p class="workspace-note workspace-note--error">{actionError(form?.createPhase)}</p>
        {/if}
        <div class="workspace-unit-commandbar-popover__actions">
          <button class="workspace-link-action" type="submit">Anlegen</button>
        </div>
      </form>
    </div>
  {/if}
  {#if showCreateModuleDialog()}
    <div class="workspace-unit-commandbar-popover" role="dialog" aria-label="Modul hinzufügen">
      <div class="workspace-unit-commandbar-popover__header">
        <div>
          <p class="workspace-label">Canvas</p>
          <h2>Modul hinzufügen</h2>
        </div>
        <button class="workspace-link-action workspace-link-action--subtle" type="button" onclick={closeCreateModuleDialog}>
          Schließen
        </button>
      </div>
      <form method="POST" action="?/createModule" class="workspace-form workspace-form--compact" use:enhance={enhanceGraphForm}>
        <label class="workspace-field">
          <span>Titel</span>
          <input name="title" type="text" value={createModuleValues().title ?? ""} />
        </label>
        <label class="workspace-field">
          <span>Phase</span>
          <select name="phase_id">
            <option value="">Bitte wählen</option>
            {#each modularPhases() as phase}
              <option
                value={phase.id}
                selected={(createModuleValues().phase_id ?? selectedPhaseId()) === phase.id}
              >
                {phase.title}
              </option>
            {/each}
          </select>
        </label>
        {#if actionError(form?.createModule)}
          <p class="workspace-note workspace-note--error">{actionError(form?.createModule)}</p>
        {/if}
        <div class="workspace-unit-commandbar-popover__actions">
          <button class="workspace-link-action" type="submit">Anlegen</button>
        </div>
      </form>
    </div>
  {/if}
  {#if showCreateSectionDialog()}
    <div class="workspace-unit-commandbar-popover" role="dialog" aria-label="Abschnitt hinzufügen">
      <div class="workspace-unit-commandbar-popover__header">
        <div>
          <p class="workspace-label">Canvas</p>
          <h2>Abschnitt hinzufügen</h2>
        </div>
        <button class="workspace-link-action workspace-link-action--subtle" type="button" onclick={closeCreateSectionDialog}>
          Schließen
        </button>
      </div>
      <form method="POST" action="?/createSection" class="workspace-form workspace-form--compact" use:enhance={enhanceGraphForm}>
        <label class="workspace-field">
          <span>Titel</span>
          <input name="title" type="text" value={createSectionValues().title ?? ""} />
        </label>
        {#if actionError(form?.createSection)}
          <p class="workspace-note workspace-note--error">{actionError(form?.createSection)}</p>
        {/if}
        <div class="workspace-unit-commandbar-popover__actions">
          <button class="workspace-link-action" type="submit">Anlegen</button>
        </div>
      </form>
    </div>
  {/if}
{/snippet}

<TeacherGraphWorkspaceFrame
  backHref="/teaching/units"
  backLabel="Zurück zu Lerneinheiten"
  title={workspaceState.unit.title}
  copy={workspaceState.unit.unit_type === "linear"
    ? `${workspaceState.counts.sections_count} Abschnitte · dieselbe Graphansicht wie für Lernende`
    : `${workspaceState.counts.phases_count} Phasen · ${workspaceState.counts.modules_count} Module · dieselbe Graphansicht wie für Lernende`}
  headerActions={unitHeaderActions}
  commandBarActions={graphCommandActions()}
  commandBarPopovers={unitCommandPopovers}
  inspectorOpen={quickEditOpen() && localSelection.kind !== "none" && localSelection.kind !== "edge" && localSelection.kind !== "module"}
>
  {#snippet canvas()}
    <SvelteFlow
      bind:nodes={flowNodes}
      bind:edges={flowEdges}
      bind:viewport={flowViewport}
      class="teacher-flow-canvas"
      {nodeTypes}
      {edgeTypes}
      fitView
      fitViewOptions={{ padding: 0.24, minZoom: 0.68, maxZoom: 1.02 }}
      minZoom={0.52}
      maxZoom={1.26}
      elementsSelectable={false}
      nodesFocusable={false}
      panOnDrag={true}
      selectNodesOnDrag={false}
      nodesDraggable={!flowBusy}
      onnodeclick={handleNodeClick}
      onedgeclick={handleEdgeClick}
      onpaneclick={handlePaneClick}
      onconnect={handleConnect}
      onnodedragstop={handleNodeDragStop}
    >
      <Controls position="bottom-right" />

      {#if graphMessage}
        <Panel position="top-center">
          <p class={`teacher-flow-status teacher-flow-status--${graphMessage.tone}`}>{graphMessage.text}</p>
        </Panel>
      {/if}
    </SvelteFlow>
  {/snippet}

  {#snippet inspector()}
    <GraphInspectorPanel
      eyebrow="Property inspector"
      title={localSelection.kind === "section" ? "Abschnitt bearbeiten" : "Phase bearbeiten"}
      closeHref={pageHref({ quick: null })}
    >
      {#snippet children()}
        {#if localSelection.kind === "section"}
          <form method="POST" action="?/saveSection" class="workspace-form workspace-form--compact" use:enhance={enhanceGraphForm}>
            <input type="hidden" name="section_id" value={localSelection.section.id} />
            <label class="workspace-field">
              <span>Name</span>
              <input name="title" type="text" value={localSelection.section.title} />
            </label>
            {#if actionError(form?.saveSection)}
              <p class="workspace-note workspace-note--error">{actionError(form?.saveSection)}</p>
            {/if}
            <div class="workspace-unit-commandbar-popover__actions">
              <button class="workspace-link-action" type="submit">Speichern</button>
              <a class="workspace-link-action workspace-link-action--subtle" href={localSelection.section.editor_href}>
                Inhalt bearbeiten
              </a>
            </div>
          </form>
        {:else if localSelection.kind === "phase"}
          <form method="POST" action="?/savePhase" class="workspace-form workspace-form--compact" use:enhance={enhanceGraphForm}>
            <input type="hidden" name="phase_id" value={localSelection.phase.id} />
            <label class="workspace-field">
              <span>Name</span>
              <input name="title" type="text" value={localSelection.phase.title} />
            </label>
            {#if actionError(form?.savePhase)}
              <p class="workspace-note workspace-note--error">{actionError(form?.savePhase)}</p>
            {/if}
            <div class="workspace-unit-commandbar-popover__actions">
              <button class="workspace-link-action" type="submit">Speichern</button>
              <button class="workspace-link-action workspace-link-action--subtle" type="button" onclick={() => moveSelectedPhase(-1)}>
                Nach oben
              </button>
              <button class="workspace-link-action workspace-link-action--subtle" type="button" onclick={() => moveSelectedPhase(1)}>
                Nach unten
              </button>
              <button class="workspace-link-action workspace-link-action--subtle" type="button" onclick={openCreateModuleDialog}>
                Modul hinzufügen
              </button>
            </div>
          </form>
        {/if}
      {/snippet}

      {#snippet footer()}
        {#if localSelection.kind === "section"}
          <form method="POST" action="?/deleteSection" class="workspace-form" use:enhance={enhanceGraphForm}>
            <input type="hidden" name="section_id" value={localSelection.section.id} />
            <button class="workspace-link-action workspace-link-action--danger" type="submit">Abschnitt löschen</button>
          </form>
        {:else if localSelection.kind === "phase"}
          <form method="POST" action="?/deletePhase" class="workspace-form" use:enhance={enhanceGraphForm}>
            <input type="hidden" name="phase_id" value={localSelection.phase.id} />
            <button class="workspace-link-action workspace-link-action--danger" type="submit">Phase löschen</button>
          </form>
        {/if}
      {/snippet}
    </GraphInspectorPanel>
  {/snippet}
</TeacherGraphWorkspaceFrame>

{#if data.showEditDialog}
  <div class="dialog-backdrop">
    <div class="dialog-card">
      <div class="dialog-card__header">
        <div>
          <p class="workspace-label">Lerneinheit</p>
          <h2>Bearbeiten</h2>
        </div>
        <a class="workspace-link-action workspace-link-action--subtle" href={pageHref({ edit: null })}>Schließen</a>
      </div>
      <form method="POST" action="?/saveUnit" class="workspace-form">
        <label class="workspace-field">
          <span>Titel</span>
          <input name="title" type="text" value={form?.saveUnit?.values?.title ?? workspaceState.unit.title} />
        </label>
        <label class="workspace-field">
          <span>Zusammenfassung</span>
          <textarea name="summary" rows="4">{form?.saveUnit?.values?.summary ?? workspaceState.unit.summary ?? ""}</textarea>
        </label>
        {#if form?.saveUnit?.error}
          <p class="workspace-note workspace-note--error">{form.saveUnit.error}</p>
        {/if}
        <div class="dialog-card__actions">
          <button class="workspace-link-action" type="submit">Speichern</button>
          <a class="workspace-link-action workspace-link-action--subtle" href={pageHref({ edit: null })}>Abbrechen</a>
        </div>
      </form>
    </div>
  </div>
{/if}

{#if data.showDeleteDialog}
  <div class="dialog-backdrop">
    <div class="dialog-card" role="dialog" aria-modal="true" aria-labelledby="delete-unit-title">
      <div class="dialog-card__header">
        <div>
          <p class="workspace-label">Lerneinheit</p>
          <h2 id="delete-unit-title">Endgültig löschen</h2>
        </div>
        <a class="workspace-link-action workspace-link-action--subtle" href={pageHref({ delete: null })}>Schließen</a>
      </div>
      <p class="workspace-note">
        Diese Lerneinheit ist {workspaceState.counts.courses_count === 1
          ? "einem Kurs"
          : `${workspaceState.counts.courses_count} Kursen`} zugeordnet. Beim Löschen werden diese Kurszuordnungen entfernt.
      </p>
      <form method="POST" action="?/deleteUnit" class="workspace-form">
        <input type="hidden" name="expected_title" value={workspaceState.unit.title} />
        <label class="workspace-field">
          <span>Titel zur Bestätigung</span>
          <input name="confirmation" type="text" autocomplete="off" />
        </label>
        {#if form?.deleteUnit?.error}
          <p class="workspace-note workspace-note--error">{form.deleteUnit.error}</p>
        {/if}
        <div class="dialog-card__actions">
          <button class="workspace-link-action workspace-link-action--danger" type="submit">Lerneinheit endgültig löschen</button>
          <a class="workspace-link-action workspace-link-action--subtle" href={pageHref({ delete: null })}>Abbrechen</a>
        </div>
      </form>
    </div>
  </div>
{/if}
