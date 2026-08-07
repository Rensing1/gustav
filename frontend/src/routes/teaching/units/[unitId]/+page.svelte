<script lang="ts">
  import { enhance } from "$app/forms";
  import { goto, invalidateAll, replaceState } from "$app/navigation";
  import { page } from "$app/state";
  import {
    Controls,
    Panel,
    SvelteFlow,
    type Connection
  } from "@xyflow/svelte";
  import "@xyflow/svelte/dist/style.css";
  import type { SubmitFunction } from "@sveltejs/kit";

  import GraphDeleteDialog from "$lib/components/teacher-unit-graph/GraphDeleteDialog.svelte";
  import GraphPhaseBand from "$lib/components/teacher-unit-graph/GraphPhaseBand.svelte";
  import type { TeacherGraphCommandBarAction } from "$lib/components/teacher-unit-graph/TeacherGraphCommandBar.svelte";
  import TeacherGraphEdge from "$lib/components/teacher-unit-graph/TeacherGraphEdge.svelte";
  import GraphUnitNode from "$lib/components/teacher-unit-graph/GraphUnitNode.svelte";
  import GraphInspectorPanel from "$lib/components/ui/GraphInspectorPanel.svelte";
  import TeacherGraphWorkspaceFrame from "$lib/components/ui/TeacherGraphWorkspaceFrame.svelte";
  import { handleBrowserAuthRecovery } from "$lib/utils/browser-auth-recovery";
  import {
    buildTeacherUnitFlow,
    type TeacherFlowEdge,
    type TeacherFlowEdgeData,
    type TeacherFlowNode,
    type TeacherFlowNodeData
  } from "$lib/graph/teacher-unit-flow";
  import type {
    TeacherUnitWorkspaceView,
    TeacherUnitWorkspaceSelection
  } from "$lib/types/home";
  import {
    cloneWorkspace,
    deriveEdgeSelection as deriveWorkspaceEdgeSelection,
    deriveModuleSelection as deriveWorkspaceModuleSelection,
    derivePhaseSelection as deriveWorkspacePhaseSelection,
    deriveSectionSelection as deriveWorkspaceSectionSelection,
    modularPhases as workspaceModularPhases,
    workspaceGraphSignature
  } from "$lib/teacher-unit-workspace/view-state";
  import {
    actionError,
    actionValues,
    asGraphActionSuccess,
    graphActionSuccessFromResult
  } from "$lib/teacher-unit-workspace/graph-action-result";
  import {
    graphDeletionImpact,
    type GraphDeletionTarget
  } from "$lib/teacher-unit-workspace/graph-deletion-impact";
  import type { ActionData, PageData } from "./$types";

  let { data, form }: { data: PageData; form: ActionData } = $props();

  function initialWorkspace(): TeacherUnitWorkspaceView {
    return cloneWorkspace(data.workspace);
  }

  let flowNodes = $state.raw<TeacherFlowNode[]>([]);
  let flowEdges = $state.raw<TeacherFlowEdge[]>([]);
  let flowBusy = $state(false);
  let graphMessage = $state<{ tone: "info" | "success" | "error"; text: string } | null>(null);
  let workspaceState = $state<TeacherUnitWorkspaceView>(initialWorkspace());
  let localSelection = $state<TeacherUnitWorkspaceSelection>({ kind: "none" });
  let handledForm: ActionData | undefined = undefined;
  let initialCreateDialogStateApplied = $state(false);
  type StructurePanelMode = "create-phase" | "create-module" | "edit-phase" | "edit-module" | null;
  let structurePanelMode = $state<StructurePanelMode>(null);
  let deleteTarget = $state<GraphDeletionTarget | null>(null);
  let inspectorReturnFocus = $state<HTMLElement | null>(null);
  let createSectionOpen = $state(false);
  let flowViewport = $state<{ x: number; y: number; zoom: number } | undefined>(undefined);
  let lastWorkspaceSignature = "";
  let pendingViewportReset = false;
  let flowBuildSequence = 0;
  let lastQuickSelectionKey = "";

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
      if (success) {
        const targetHref = success.next ? pageHref(success.next) : null;
        const deleted = deleteTarget !== null;
        const created = structurePanelMode === "create-phase" || structurePanelMode === "create-module";
        if (deleted) {
          deleteTarget = null;
          structurePanelMode = success.next?.module
            ? "edit-module"
            : success.next?.phase
              ? "edit-phase"
              : null;
        } else if (created) {
          structurePanelMode = success.next?.module ? "edit-module" : success.next?.phase ? "edit-phase" : null;
        }
        closeCreateDialogsFromNext(success.next);
        // Keep the action result (including its success message), but reload
        // the workspace only once the URL selects the created or neighbouring
        // graph item. A shallow URL replacement alone would leave stale page
        // data and an empty inspector behind.
        await update({ reset: true, invalidateAll: false });
        if (targetHref) {
          await goto(targetHref, {
            replaceState: true,
            invalidateAll: true,
            keepFocus: true,
            noScroll: true
          });
        } else {
          await invalidateAll();
        }
        if (deleted || created) {
          focusGraphTarget(success.next);
        }
        return;
      }
      await update({ reset: false });
    };
  };

  function createPhaseValues() {
    return actionValues<{ title: string; after_phase_id: string }>(form?.createPhase);
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
    return structurePanelMode === "create-phase"
      || (!initialCreateDialogStateApplied && Boolean(data.showCreatePhaseDialog || form?.createPhase));
  }

  function showCreateModuleDialog(): boolean {
    return structurePanelMode === "create-module"
      || (!initialCreateDialogStateApplied && Boolean(data.showCreateModuleDialog || form?.createModule));
  }

  function showCreateSectionDialog(): boolean {
    return createSectionOpen || (!initialCreateDialogStateApplied && Boolean(data.showCreateSectionDialog || form?.createSection));
  }

  function selectedPhaseId(): string | null {
    // The URL is the durable graph selection. It may already point at a newly
    // created phase while the invalidated workspace response is still settling.
    const phaseFromUrl = currentUrl().searchParams.get("phase");
    if (phaseFromUrl) {
      return phaseFromUrl;
    }
    if (localSelection.kind === "phase") {
      return localSelection.phase.id;
    }
    if (localSelection.kind === "module") {
      return localSelection.module.phase_id;
    }
    return null;
  }

  function flowNodeData(node: TeacherFlowNode): TeacherFlowNodeData {
    return node.data as TeacherFlowNodeData;
  }

  function flowEdgeData(edge: TeacherFlowEdge): TeacherFlowEdgeData {
    return (edge.data as TeacherFlowEdgeData | undefined) ?? { from: edge.source, to: edge.target };
  }

  function openCreatePhaseDialog() {
    setStructurePanelMode(structurePanelMode === "create-phase" ? null : "create-phase");
  }

  function openCreateModuleDialog() {
    setStructurePanelMode(structurePanelMode === "create-module" ? null : "create-module");
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
    if (next?.["create-section"] === null) {
      createSectionOpen = false;
    }
  }

  function setStructurePanelMode(mode: StructurePanelMode) {
    if (mode !== null && structurePanelMode === null && document.activeElement instanceof HTMLElement) {
      inspectorReturnFocus = document.activeElement === document.body ? null : document.activeElement;
    }
    const returnFocus = mode === null ? inspectorReturnFocus : null;
    structurePanelMode = mode;
    const next: Record<string, string | null> = {
      "create-phase": null,
      "create-module": null,
      quick: mode === "edit-phase" || mode === "edit-module" ? "1" : null
    };
    if (mode === "create-phase") {
      next["create-phase"] = "1";
    } else if (mode === "create-module") {
      next["create-module"] = "1";
    }
    replaceCurrentUrl(pageHref(next));
    if (mode === null) {
      // Allow the currently selected graph item to reopen its inspector after
      // the user closed it. Otherwise the route-sync effect would mistake the
      // next click for the already handled `quick=1` selection.
      lastQuickSelectionKey = "";
      inspectorReturnFocus = null;
      requestAnimationFrame(() => {
        if (returnFocus?.isConnected) {
          returnFocus.focus();
          return;
        }
        focusGraphTarget(
          localSelection.kind === "module"
            ? { module: localSelection.module.id }
            : localSelection.kind === "phase"
              ? { phase: localSelection.phase.id }
              : undefined
        );
      });
    }
  }

  function openDeleteDialog(target: GraphDeletionTarget) {
    deleteTarget = target;
  }

  function closeDeleteDialog() {
    deleteTarget = null;
  }

  function openSelectedPhaseDeleteDialog() {
    if (localSelection.kind === "phase") {
      openDeleteDialog({ kind: "phase", id: localSelection.phase.id });
    }
  }

  function openSelectedModuleDeleteDialog() {
    if (localSelection.kind === "module") {
      openDeleteDialog({ kind: "module", id: localSelection.module.id });
    }
  }

  function focusWhenMounted(node: HTMLElement) {
    queueMicrotask(() => node.focus());
  }

  function focusGraphTarget(next: Record<string, string | null> | undefined) {
    const targetId = next?.module ?? next?.phase ?? null;
    const flowNodeId = next?.phase ? `phase:${next.phase}` : next?.module ?? null;
    const selector = targetId && flowNodeId
      ? `.svelte-flow__node[data-id="${flowNodeId}"]`
      : ".teacher-flow-workspace__canvas";

    const tryFocus = (attempt: number) => {
      const target = document.querySelector<HTMLElement>(selector);
      if (target) {
        target.focus();
      } else if (attempt < 8) {
        requestAnimationFrame(() => tryFocus(attempt + 1));
      }
    };
    requestAnimationFrame(() => tryFocus(0));
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
    return workspaceModularPhases(workspace);
  }

  function deriveSectionSelection(sectionId: string): TeacherUnitWorkspaceSelection {
    return deriveWorkspaceSectionSelection(workspaceState, sectionId);
  }

  function derivePhaseSelection(phaseId: string): TeacherUnitWorkspaceSelection {
    return deriveWorkspacePhaseSelection(workspaceState, phaseId);
  }

  function deriveModuleSelection(moduleId: string): TeacherUnitWorkspaceSelection {
    return deriveWorkspaceModuleSelection(workspaceState, moduleId);
  }

  function deriveEdgeSelection(fromId: string, toId: string): TeacherUnitWorkspaceSelection {
    return deriveWorkspaceEdgeSelection(workspaceState, fromId, toId);
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

    if (handleBrowserAuthRecovery(response)) {
      throw new Error("auth_recovery_started");
    }
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
      const layout = await buildTeacherUnitFlow(workspaceForBuild, selection);
      if (buildSequence !== flowBuildSequence) {
        return;
      }
      flowNodes = layout.nodes;
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
    if (data.showCreatePhaseDialog || form?.createPhase) {
      structurePanelMode = "create-phase";
    } else if (data.showCreateModuleDialog || form?.createModule) {
      structurePanelMode = "create-module";
    } else if (quickEditOpen() && data.workspace.selection.kind === "phase") {
      structurePanelMode = "edit-phase";
    } else if (quickEditOpen() && data.workspace.selection.kind === "module") {
      structurePanelMode = "edit-module";
    }
    createSectionOpen = Boolean(data.showCreateSectionDialog);
  });

  $effect(() => {
    const quick = page.url.searchParams.get("quick");
    const selection = data.workspace.selection;
    const selectionId =
      selection.kind === "phase"
        ? selection.phase.id
        : selection.kind === "module"
          ? selection.module.id
          : "none";
    const key = `${quick ?? ""}:${selection.kind}:${selectionId}`;
    if (key === lastQuickSelectionKey) {
      return;
    }
    lastQuickSelectionKey = key;
    if (quick !== "1") {
      return;
    }
    if (selection.kind === "phase") {
      structurePanelMode = "edit-phase";
      focusGraphTarget({ phase: selection.phase.id });
    } else if (selection.kind === "module") {
      structurePanelMode = "edit-module";
      focusGraphTarget({ module: selection.module.id });
    }
  });

  $effect(() => {
    const nextWorkspaceSignature = workspaceGraphSignature(data.workspace);
    const workspaceChanged = Boolean(lastWorkspaceSignature && nextWorkspaceSignature !== lastWorkspaceSignature);
    if (workspaceChanged) {
      pendingViewportReset = true;
    }
    lastWorkspaceSignature = nextWorkspaceSignature;
    const nextWorkspace = cloneWorkspace(data.workspace);
    workspaceState = nextWorkspace;
    localSelection = data.workspace.selection;
  });

  $effect(() => {
    workspaceState;
    localSelection;
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
      structurePanelMode = "create-phase";
    }
    if (actionError(form.createModule)) {
      structurePanelMode = "create-module";
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
      if (createPhaseSuccess) {
        structurePanelMode = "edit-phase";
      }
      if (createModuleSuccess) {
        structurePanelMode = "edit-module";
      }
      if (createSectionSuccess) {
        closeCreateSectionDialog();
      }
    }

    const deletePhaseValues = actionValues<{ phase_id: string }>(form.deletePhase);
    const deleteModuleValues = actionValues<{ module_id: string }>(form.deleteModule);
    if (actionError(form.deletePhase) && deletePhaseValues.phase_id) {
      deleteTarget = { kind: "phase", id: deletePhaseValues.phase_id };
    }
    if (actionError(form.deleteModule) && deleteModuleValues.module_id) {
      deleteTarget = { kind: "module", id: deleteModuleValues.module_id };
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
      const detail = error instanceof Error ? error.message : "";
      if (detail === "auth_recovery_started") {
        return;
      }
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
      if (detail === "auth_recovery_started") {
        return;
      }
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
      if (detail === "auth_recovery_started") {
        return;
      }
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
      await applyLocalSelection(deriveSectionSelection(node.id));
      return;
    }
    if (nodeData.kind === "phase") {
      const phaseId = nodeData.phaseId ?? node.id.replace(/^phase:/, "");
      await applyLocalSelection(derivePhaseSelection(phaseId));
      setStructurePanelMode("edit-phase");
      return;
    }
    if (nodeData.kind === "module") {
      await applyLocalSelection(deriveModuleSelection(node.id));
      setStructurePanelMode("edit-module");
    }
  }

  async function handleEdgeClick({ edge, event }: { edge: TeacherFlowEdge; event: MouseEvent }) {
    if (isInteractiveTarget(event.target)) {
      return;
    }

    const edgeData = flowEdgeData(edge);
    setStructurePanelMode(null);
    await applyLocalSelection(deriveEdgeSelection(edgeData.from, edgeData.to));
  }

  async function handlePaneClick() {
    await applyLocalSelection({ kind: "none" });
    inspectorReturnFocus = null;
    setStructurePanelMode(null);
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
      const detail = error instanceof Error ? error.message : "";
      if (detail === "auth_recovery_started") {
        return;
      }
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

  function inspectorOpen(): boolean {
    if (workspaceState.graph.kind === "linear") {
      return quickEditOpen() && localSelection.kind === "section";
    }
    return structurePanelMode !== null;
  }

  function inspectorTitle(): string {
    if (structurePanelMode === "create-phase") return "Phase hinzufügen";
    if (structurePanelMode === "create-module") return "Modul hinzufügen";
    if (structurePanelMode === "edit-module") return "Modul bearbeiten";
    if (structurePanelMode === "edit-phase") return "Phase bearbeiten";
    return "Abschnitt bearbeiten";
  }

  function closeInspector() {
    if (workspaceState.graph.kind === "modular") {
      setStructurePanelMode(null);
      return;
    }
    syncUrlPatch({ quick: null });
  }

  function phaseInsertionAnchor(): string {
    return createPhaseValues().after_phase_id ?? selectedPhaseId() ?? "";
  }

  function createModulePhaseId(): string {
    return createModuleValues().phase_id ?? selectedPhaseId() ?? modularPhases()[0]?.id ?? "";
  }

  function currentDeletionImpact() {
    return deleteTarget ? graphDeletionImpact(workspaceState, deleteTarget) : null;
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
  {#if showCreateSectionDialog()}
    <div class="workspace-unit-commandbar-popover" role="dialog" aria-label="Abschnitt hinzufügen">
      <div class="workspace-unit-commandbar-popover__header">
        <div>
          <p class="workspace-label">Struktur</p>
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
  inspectorOpen={inspectorOpen()}
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
      nodesFocusable={true}
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
      eyebrow="Struktur"
      title={inspectorTitle()}
      onClose={closeInspector}
    >
      {#snippet children()}
        {#if structurePanelMode === "create-phase"}
          <form method="POST" action="?/createPhase" class="workspace-form workspace-form--compact" use:enhance={enhanceGraphForm}>
            <input name="after_phase_id" type="hidden" value={phaseInsertionAnchor()} />
            <label class="workspace-field">
              <span>Titel</span>
              <input name="title" type="text" value={createPhaseValues().title ?? ""} use:focusWhenMounted />
            </label>
            {#if phaseInsertionAnchor()}
              <p class="workspace-note">Die neue Phase wird hinter der ausgewählten Phase eingefügt.</p>
            {/if}
            {#if actionError(form?.createPhase)}
              <p class="workspace-note workspace-note--error">{actionError(form?.createPhase)}</p>
            {/if}
            <div class="workspace-unit-commandbar-popover__actions">
              <button class="workspace-link-action" type="submit">Phase anlegen</button>
            </div>
          </form>
        {:else if structurePanelMode === "create-module"}
          {#if modularPhases().length === 0}
            <div class="workspace-form workspace-form--compact">
              <p class="workspace-note">Lege zuerst eine Phase an, der das Modul zugeordnet werden kann.</p>
              <button class="workspace-link-action" type="button" onclick={openCreatePhaseDialog}>Phase anlegen</button>
            </div>
          {:else}
            <form method="POST" action="?/createModule" class="workspace-form workspace-form--compact" use:enhance={enhanceGraphForm}>
              <label class="workspace-field">
                <span>Titel</span>
                <input name="title" type="text" value={createModuleValues().title ?? ""} use:focusWhenMounted />
              </label>
              <label class="workspace-field">
                <span>Phase</span>
                <select name="phase_id">
                  {#each modularPhases() as phase}
                    <option value={phase.id} selected={createModulePhaseId() === phase.id}>{phase.title}</option>
                  {/each}
                </select>
              </label>
              {#if actionError(form?.createModule)}
                <p class="workspace-note workspace-note--error">{actionError(form?.createModule)}</p>
              {/if}
              <div class="workspace-unit-commandbar-popover__actions">
                <button class="workspace-link-action" type="submit">Modul anlegen</button>
              </div>
            </form>
          {/if}
        {:else if localSelection.kind === "section"}
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
        {:else if structurePanelMode === "edit-phase" && localSelection.kind === "phase"}
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
        {:else if structurePanelMode === "edit-module" && localSelection.kind === "module"}
          <form method="POST" action="?/saveModule" class="workspace-form workspace-form--compact" use:enhance={enhanceGraphForm}>
            <input type="hidden" name="module_id" value={localSelection.module.id} />
            <input type="hidden" name="current_phase_id" value={localSelection.module.phase_id} />
            <label class="workspace-field">
              <span>Name</span>
              <input
                name="title"
                type="text"
                value={actionValues<{ title: string }>(form?.saveModule).title ?? localSelection.module.title}
              />
            </label>
            <label class="workspace-field">
              <span>Phase</span>
              <select name="phase_id">
                {#each modularPhases() as phase}
                  <option
                    value={phase.id}
                    selected={(actionValues<{ phase_id: string }>(form?.saveModule).phase_id ?? localSelection.module.phase_id) === phase.id}
                  >
                    {phase.title}
                  </option>
                {/each}
              </select>
            </label>
            <label class="workspace-field">
              <span>Freischaltung</span>
              <input
                name="required_prereq_count"
                type="number"
                min="0"
                value={actionValues<{ required_prereq_count: string }>(form?.saveModule).required_prereq_count
                  ?? String(localSelection.module.required_prereq_count)}
              />
            </label>
            {#if actionError(form?.saveModule)}
              <p class="workspace-note workspace-note--error">{actionError(form?.saveModule)}</p>
            {/if}
            <div class="workspace-unit-commandbar-popover__actions">
              <button class="workspace-link-action" type="submit">Speichern</button>
              <a class="workspace-link-action workspace-link-action--subtle" href={localSelection.module.editor_href}>
                Inhalt bearbeiten
              </a>
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
        {:else if structurePanelMode === "edit-phase" && localSelection.kind === "phase"}
          <button
            class="workspace-link-action workspace-link-action--danger"
            type="button"
            onclick={openSelectedPhaseDeleteDialog}
          >
            Phase löschen
          </button>
        {:else if structurePanelMode === "edit-module" && localSelection.kind === "module"}
          <button
            class="workspace-link-action workspace-link-action--danger"
            type="button"
            onclick={openSelectedModuleDeleteDialog}
          >
            Modul löschen
          </button>
        {/if}
      {/snippet}
    </GraphInspectorPanel>
  {/snippet}
</TeacherGraphWorkspaceFrame>

{#if currentDeletionImpact()}
  <GraphDeleteDialog
    impact={currentDeletionImpact()!}
    action={currentDeletionImpact()!.kind === "phase" ? "?/deletePhase" : "?/deleteModule"}
    error={currentDeletionImpact()!.kind === "phase" ? actionError(form?.deletePhase) : actionError(form?.deleteModule)}
    onCancel={closeDeleteDialog}
    enhanceForm={enhanceGraphForm}
  />
{/if}

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
