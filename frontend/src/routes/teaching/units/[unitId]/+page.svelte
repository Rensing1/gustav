<script lang="ts">
  import { invalidateAll } from "$app/navigation";
  import { page } from "$app/state";
  import {
    Controls,
    Panel,
    SvelteFlow,
    type Connection
  } from "@xyflow/svelte";
  import "@xyflow/svelte/dist/style.css";

  import GraphPhaseBand from "$lib/components/teacher-unit-graph/GraphPhaseBand.svelte";
  import GraphUnitNode from "$lib/components/teacher-unit-graph/GraphUnitNode.svelte";
  import {
    buildTeacherUnitFlow,
    type TeacherFlowEdge,
    type TeacherFlowEdgeData,
    type TeacherFlowNode,
    type TeacherFlowNodeData
  } from "$lib/graph/teacher-unit-flow";
  import type {
    TeacherUnitWorkspaceEdgeSelection,
    TeacherUnitWorkspaceGraphPhase,
    TeacherUnitWorkspaceModuleItem,
    TeacherUnitWorkspaceSectionItem,
    TeacherUnitWorkspaceSelection
  } from "$lib/types/home";
  import type { ActionData, PageData } from "./$types";

  let { data, form }: { data: PageData; form: ActionData } = $props();

  let flowNodes = $state.raw<TeacherFlowNode[]>([]);
  let flowEdges = $state.raw<TeacherFlowEdge[]>([]);
  let flowBusy = $state(false);
  let graphMessage = $state<{ tone: "info" | "success" | "error"; text: string } | null>(null);
  let localSelection = $state<TeacherUnitWorkspaceSelection>({ kind: "none" });

  const nodeTypes = {
    unitNode: GraphUnitNode,
    phaseBand: GraphPhaseBand
  };

  function pageHref(next: Record<string, string | null>): string {
    const baseUrl = typeof window === "undefined" ? new URL(page.url) : new URL(window.location.href);
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
    return page.url.searchParams.get("quick") === "1";
  }

  function selectedPhaseId(): string | null {
    if (localSelection.kind === "phase") {
      return localSelection.phase.id;
    }
    if (localSelection.kind === "module") {
      return localSelection.module.phase_id;
    }
    return page.url.searchParams.get("phase");
  }

  function flowNodeData(node: TeacherFlowNode): TeacherFlowNodeData {
    return node.data as TeacherFlowNodeData;
  }

  function flowEdgeData(edge: TeacherFlowEdge): TeacherFlowEdgeData {
    return (edge.data as TeacherFlowEdgeData | undefined) ?? { from: edge.source, to: edge.target };
  }

  function isInteractiveTarget(target: EventTarget | null): boolean {
    return target instanceof Element && Boolean(target.closest("a,button,summary,input,textarea,select,label,form"));
  }

  function modularPhases() {
    return data.workspace.graph.kind === "modular" ? (data.workspace.graph.phases ?? []) : [];
  }

  function graphSections(): TeacherUnitWorkspaceSectionItem[] {
    return data.workspace.graph.kind === "linear" ? (data.workspace.graph.nodes ?? []) : [];
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
    return (data.workspace.graph.edges ?? []).some((edge) => edge.from === fromId && edge.to === toId);
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

    const url = new URL(window.location.href);
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

    window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}${url.hash}`);
  }

  async function applyLocalSelection(selection: TeacherUnitWorkspaceSelection) {
    localSelection = selection;
    syncSelectionUrl(selection);
    await rebuildFlow(selection);
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
      let errorPayload: { detail?: string } = {};
      try {
        errorPayload = await response.json();
      } catch {
        errorPayload = {};
      }
      throw new Error(errorPayload.detail || "request_failed");
    }

    if (response.status === 204) {
      return null;
    }
    return response.json();
  }

  async function refreshWorkspace() {
    await invalidateAll();
  }

  async function rebuildFlow(selection: TeacherUnitWorkspaceSelection = localSelection) {
    flowBusy = true;
    try {
      const layout = await buildTeacherUnitFlow(data.workspace, selection);
      flowNodes = layout.nodes;
      flowEdges = layout.edges;
    } finally {
      flowBusy = false;
    }
  }

  $effect(() => {
    data.workspace;
    localSelection = data.workspace.selection;
    void rebuildFlow(data.workspace.selection);
  });

  function orderedSectionIds(): string[] {
    return flowNodes
      .filter((node) => flowNodeData(node).kind === "section")
      .sort((left, right) => left.position.y - right.position.y)
      .map((node) => node.id);
  }

  async function persistSectionReorder() {
    if (data.workspace.graph.kind !== "linear") {
      return;
    }

    const current = (data.workspace.graph.nodes ?? []).map((node) => node.id);
    const next = orderedSectionIds();

    if (JSON.stringify(current) === JSON.stringify(next)) {
      return;
    }

    try {
      await apiJson("POST", `/api/teaching/units/${data.workspace.unit.id}/sections/reorder`, { section_ids: next });
      setGraphMessage("Abschnitte gespeichert.", "success");
      await refreshWorkspace();
    } catch (error) {
      setGraphMessage("Abschnitte konnten nicht neu geordnet werden.", "error");
      await rebuildFlow(localSelection);
    }
  }

  function phaseBandNodes(): TeacherFlowNode[] {
    return flowNodes
      .filter((node) => flowNodeData(node).kind === "phase")
      .sort((left, right) => left.position.y - right.position.y);
  }

  function moduleNodes(): TeacherFlowNode[] {
    return flowNodes.filter((node) => flowNodeData(node).kind === "module");
  }

  function targetPhaseIdForNode(node: TeacherFlowNode): string | null {
    const nodeCenter = node.position.y + (node.height ?? 0) / 2;
    const lanes = phaseBandNodes();
    if (!lanes.length) {
      return null;
    }

    let bestPhase = flowNodeData(lanes[0]).phaseId ?? null;
    let bestDistance = Number.POSITIVE_INFINITY;

    for (const lane of lanes) {
      const laneData = flowNodeData(lane);
      const laneHeight = laneData.bandHeight ?? lane.height ?? 0;
      const laneTop = lane.position.y;
      const laneBottom = laneTop + laneHeight;

      if (nodeCenter >= laneTop && nodeCenter <= laneBottom) {
        return laneData.phaseId ?? null;
      }

      const laneCenter = laneTop + laneHeight / 2;
      const distance = Math.abs(nodeCenter - laneCenter);
      if (distance < bestDistance) {
        bestDistance = distance;
        bestPhase = laneData.phaseId ?? null;
      }
    }

    return bestPhase;
  }

  async function persistModuleReorder(nodeId: string) {
    if (data.workspace.graph.kind !== "modular") {
      return;
    }

    const movedNode = moduleNodes().find((node) => node.id === nodeId);
    if (!movedNode) {
      return;
    }

    const targetPhaseId = targetPhaseIdForNode(movedNode);
    if (!targetPhaseId) {
      await rebuildFlow(localSelection);
      return;
    }

    const nextIds = moduleNodes()
      .filter((node) => {
        const nodeData = flowNodeData(node);
        const phaseId = node.id === nodeId ? targetPhaseId : nodeData.phaseId;
        return phaseId === targetPhaseId;
      })
      .sort((left, right) => left.position.x - right.position.x)
      .map((node) => node.id);

    const currentIds =
      modularPhases()
        .find((phase) => phase.id === targetPhaseId)
        ?.modules.map((module) => module.id) ?? [];

    if (JSON.stringify(currentIds) === JSON.stringify(nextIds)) {
      await rebuildFlow(localSelection);
      return;
    }

    try {
      await apiJson(
        "POST",
        `/api/teaching/units/${data.workspace.unit.id}/phases/${targetPhaseId}/modules/reorder`,
        { module_ids: nextIds }
      );
      setGraphMessage("Module gespeichert.", "success");
      await refreshWorkspace();
    } catch (error) {
      const detail = error instanceof Error ? error.message : "";
      const message =
        detail === "edge_constraint_violation"
          ? "Verschieben blockiert: Abhängigkeiten zuerst entfernen."
          : "Module konnten nicht neu geordnet werden.";
      setGraphMessage(message, "error");
      await rebuildFlow(localSelection);
    }
  }

  async function moveSelectedPhase(direction: -1 | 1) {
    if (data.workspace.graph.kind !== "modular" || localSelection.kind !== "phase") {
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
      await apiJson("POST", `/api/teaching/units/${data.workspace.unit.id}/phases/reorder`, {
        phase_ids: reordered
      });
      setGraphMessage("Phasen gespeichert.", "success");
      await refreshWorkspace();
    } catch (error) {
      const detail = error instanceof Error ? error.message : "";
      const message =
        detail === "edge_constraint_violation"
          ? "Phasen können wegen bestehender Abhängigkeiten nicht so verschoben werden."
          : "Phasen konnten nicht neu geordnet werden.";
      setGraphMessage(message, "error");
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
      return;
    }
    if (nodeData.kind === "module") {
      await applyLocalSelection(deriveModuleSelection(node.id));
    }
  }

  async function handleEdgeClick({ edge, event }: { edge: TeacherFlowEdge; event: MouseEvent }) {
    if (isInteractiveTarget(event.target)) {
      return;
    }

    const edgeData = flowEdgeData(edge);
    await applyLocalSelection(deriveEdgeSelection(edgeData.from, edgeData.to));
  }

  async function handlePaneClick() {
    await applyLocalSelection({ kind: "none" });
  }

  async function handleConnect(connection: Connection) {
    if (data.workspace.graph.kind !== "modular" || !connection.source || !connection.target || connection.source === connection.target) {
      return;
    }

    try {
      await apiJson("POST", `/api/teaching/units/${data.workspace.unit.id}/modules/edges`, {
        from_module_id: connection.source,
        to_module_id: connection.target
      });
      setGraphMessage("Kante angelegt.", "success");
      await refreshWorkspace();
      await applyLocalSelection(deriveEdgeSelection(connection.source, connection.target));
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
  <title>{data.workspace.unit.title} | GUSTAV</title>
</svelte:head>

<section class="workspace-composer-header workspace-unit-header">
  <div class="workspace-composer-copy">
    <a class="workspace-back-link" href="/teaching/units">Zurück zu Lerneinheiten</a>
    <h1>{data.workspace.unit.title}</h1>
    <p class="workspace-composer-copyline">
      {#if data.workspace.unit.unit_type === "linear"}
        {data.workspace.counts.sections_count} Abschnitte · gleiche Graphlogik wie für Lernende
      {:else}
        {data.workspace.counts.phases_count} Phasen · {data.workspace.counts.modules_count} Module · gleiche Graphlogik wie für Lernende
      {/if}
    </p>
  </div>

  <div class="workspace-unit-header-actions">
    <details class="workspace-row-menu">
      <summary aria-label="Einheitsaktionen">···</summary>
      <div class="workspace-row-menu-popover">
        <a class="workspace-link-action workspace-link-action--subtle" href={data.workspace.unit.edit_href}>Bearbeiten</a>
      </div>
    </details>
  </div>
</section>

<div class="teacher-flow-page-tools" role="toolbar" aria-label="Graphwerkzeuge">
  <span class="workspace-label">Canvas</span>
  {#if data.workspace.graph.kind === "linear"}
    <a class="workspace-link-action" href={data.workspace.graph.create_section_href}>Abschnitt hinzufügen</a>
  {:else}
    <a class="workspace-link-action" href={data.workspace.graph.create_phase_href}>Phase hinzufügen</a>
    <a class="workspace-link-action workspace-link-action--subtle" href={data.workspace.graph.create_module_href}>Modul hinzufügen</a>
  {/if}
</div>

<section class="teacher-flow-workspace teacher-flow-shell">
    <SvelteFlow
      bind:nodes={flowNodes}
      bind:edges={flowEdges}
      class="teacher-flow-canvas"
      {nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.24, minZoom: 0.68, maxZoom: 1.02 }}
      minZoom={0.52}
      maxZoom={1.26}
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

      {#if localSelection.kind !== "none"}
        {#if localSelection.kind === "edge"}
          <Panel position="bottom-center">
            <aside class="teacher-flow-edge-selection">
              <div class="teacher-flow-edge-selection__copy">
                <p class="workspace-label">Kante</p>
                <strong>{localSelection.edge.from_title} → {localSelection.edge.to_title}</strong>
              </div>
              {#if localSelection.edge.exists}
                <form method="POST" action="?/deleteEdge" class="teacher-flow-edge-selection__form">
                  <input type="hidden" name="from_module_id" value={localSelection.edge.from_id} />
                  <input type="hidden" name="to_module_id" value={localSelection.edge.to_id} />
                  <button class="workspace-link-action workspace-link-action--danger" type="submit">Löschen</button>
                </form>
              {:else}
                <form method="POST" action="?/createEdge" class="teacher-flow-edge-selection__form">
                  <input type="hidden" name="from_module_id" value={localSelection.edge.from_id} />
                  <input type="hidden" name="to_module_id" value={localSelection.edge.to_id} />
                  <button class="workspace-link-action" type="submit">Anlegen</button>
                </form>
              {/if}
            </aside>
          </Panel>
        {/if}
      {/if}
    </SvelteFlow>
</section>

{#if quickEditOpen() && localSelection.kind !== "none" && localSelection.kind !== "edge"}
  <div class="dialog-backdrop dialog-backdrop--light">
    <div class="dialog-card teacher-flow-quickedit">
      <div class="dialog-card__header">
        <div>
          <p class="workspace-label">Canvas</p>
          <h2>
            {#if localSelection.kind === "section"}
              Abschnitt bearbeiten
            {:else if localSelection.kind === "phase"}
              Phase bearbeiten
            {:else}
              Modul bearbeiten
            {/if}
          </h2>
        </div>
        <a class="workspace-link-action workspace-link-action--subtle" href={pageHref({ quick: null })}>Schließen</a>
      </div>

      {#if localSelection.kind === "section"}
        <form method="POST" action="?/saveSection" class="workspace-form">
          <input type="hidden" name="section_id" value={localSelection.section.id} />
          <label class="workspace-field">
            <span>Name</span>
            <input name="title" type="text" value={localSelection.section.title} />
          </label>
          {#if form?.saveSection?.error}
            <p class="workspace-note workspace-note--error">{form.saveSection.error}</p>
          {/if}
          <div class="dialog-card__actions">
            <button class="workspace-link-action" type="submit">Speichern</button>
            <a class="workspace-link-action workspace-link-action--subtle" href={localSelection.section.editor_href}>
              Inhalt bearbeiten
            </a>
          </div>
        </form>
        <div class="dialog-card__danger">
          <form method="POST" action="?/deleteSection" class="workspace-form">
            <input type="hidden" name="section_id" value={localSelection.section.id} />
            <button class="workspace-link-action workspace-link-action--danger" type="submit">Abschnitt löschen</button>
          </form>
        </div>
      {:else if localSelection.kind === "phase"}
        <form method="POST" action="?/savePhase" class="workspace-form">
          <input type="hidden" name="phase_id" value={localSelection.phase.id} />
          <label class="workspace-field">
            <span>Name</span>
            <input name="title" type="text" value={localSelection.phase.title} />
          </label>
          {#if form?.savePhase?.error}
            <p class="workspace-note workspace-note--error">{form.savePhase.error}</p>
          {/if}
          <div class="dialog-card__actions">
            <button class="workspace-link-action" type="submit">Speichern</button>
            <button class="workspace-link-action workspace-link-action--subtle" type="button" onclick={() => moveSelectedPhase(-1)}>
              Nach oben
            </button>
            <button class="workspace-link-action workspace-link-action--subtle" type="button" onclick={() => moveSelectedPhase(1)}>
              Nach unten
            </button>
            <a class="workspace-link-action workspace-link-action--subtle" href={pageHref({ "create-module": "1" })}>
              Modul hinzufügen
            </a>
          </div>
        </form>
        <div class="dialog-card__danger">
          <form method="POST" action="?/deletePhase" class="workspace-form">
            <input type="hidden" name="phase_id" value={localSelection.phase.id} />
            <button class="workspace-link-action workspace-link-action--danger" type="submit">Phase löschen</button>
          </form>
        </div>
      {:else if localSelection.kind === "module"}
        <form method="POST" action="?/saveModule" class="workspace-form">
          <input type="hidden" name="module_id" value={localSelection.module.id} />
          <label class="workspace-field">
            <span>Name</span>
            <input name="title" type="text" value={localSelection.module.title} />
          </label>
          <label class="workspace-field">
            <span>Freischaltung</span>
            <input
              name="required_prereq_count"
              type="number"
              min="0"
              value={localSelection.module.required_prereq_count}
            />
          </label>
          {#if form?.saveModule?.error}
            <p class="workspace-note workspace-note--error">{form.saveModule.error}</p>
          {/if}
          <div class="dialog-card__actions">
            <button class="workspace-link-action" type="submit">Speichern</button>
            <a class="workspace-link-action workspace-link-action--subtle" href={localSelection.module.editor_href}>
              Inhalt bearbeiten
            </a>
          </div>
        </form>
        <div class="dialog-card__danger">
          <form method="POST" action="?/deleteModule" class="workspace-form">
            <input type="hidden" name="module_id" value={localSelection.module.id} />
            <button class="workspace-link-action workspace-link-action--danger" type="submit">Modul löschen</button>
          </form>
        </div>
      {/if}
    </div>
  </div>
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
          <input name="title" type="text" value={form?.saveUnit?.values?.title ?? data.workspace.unit.title} />
        </label>
        <label class="workspace-field">
          <span>Zusammenfassung</span>
          <textarea name="summary" rows="4">{form?.saveUnit?.values?.summary ?? data.workspace.unit.summary ?? ""}</textarea>
        </label>
        {#if form?.saveUnit?.error}
          <p class="workspace-note workspace-note--error">{form.saveUnit.error}</p>
        {/if}
        <div class="dialog-card__actions">
          <button class="workspace-link-action" type="submit">Speichern</button>
          <a class="workspace-link-action workspace-link-action--subtle" href={pageHref({ edit: null })}>Abbrechen</a>
        </div>
      </form>
      <div class="dialog-card__danger">
        <p class="workspace-label">Danger Zone</p>
        <form method="POST" action="?/deleteUnit" class="workspace-form">
          <input type="hidden" name="expected_title" value={data.workspace.unit.title} />
          <label class="workspace-field">
            <span>Titel zur Bestätigung</span>
            <input name="confirmation" type="text" />
          </label>
          {#if form?.deleteUnit?.error}
            <p class="workspace-note workspace-note--error">{form.deleteUnit.error}</p>
          {/if}
          <button class="workspace-link-action workspace-link-action--danger" type="submit">Lerneinheit löschen</button>
        </form>
      </div>
    </div>
  </div>
{/if}

{#if data.showCreateSectionDialog}
  <div class="dialog-backdrop">
    <div class="dialog-card">
      <div class="dialog-card__header">
        <div><p class="workspace-label">Canvas</p><h2>Abschnitt hinzufügen</h2></div>
        <a class="workspace-link-action workspace-link-action--subtle" href={pageHref({ "create-section": null })}>Schließen</a>
      </div>
      <form method="POST" action="?/createSection" class="workspace-form">
        <label class="workspace-field">
          <span>Titel</span>
          <input name="title" type="text" value="" />
        </label>
        {#if form?.createSection?.error}
          <p class="workspace-note workspace-note--error">{form.createSection.error}</p>
        {/if}
        <div class="dialog-card__actions">
          <button class="workspace-link-action" type="submit">Anlegen</button>
        </div>
      </form>
    </div>
  </div>
{/if}

{#if data.showCreatePhaseDialog}
  <div class="dialog-backdrop">
    <div class="dialog-card">
      <div class="dialog-card__header">
        <div><p class="workspace-label">Canvas</p><h2>Phase hinzufügen</h2></div>
        <a class="workspace-link-action workspace-link-action--subtle" href={pageHref({ "create-phase": null })}>Schließen</a>
      </div>
      <form method="POST" action="?/createPhase" class="workspace-form">
        <label class="workspace-field">
          <span>Titel</span>
          <input name="title" type="text" value="" />
        </label>
        {#if form?.createPhase?.error}
          <p class="workspace-note workspace-note--error">{form.createPhase.error}</p>
        {/if}
        <div class="dialog-card__actions">
          <button class="workspace-link-action" type="submit">Anlegen</button>
        </div>
      </form>
    </div>
  </div>
{/if}

{#if data.showCreateModuleDialog}
  <div class="dialog-backdrop">
    <div class="dialog-card">
      <div class="dialog-card__header">
        <div><p class="workspace-label">Canvas</p><h2>Modul hinzufügen</h2></div>
        <a class="workspace-link-action workspace-link-action--subtle" href={pageHref({ "create-module": null })}>Schließen</a>
      </div>
      <form method="POST" action="?/createModule" class="workspace-form">
        <label class="workspace-field">
          <span>Titel</span>
          <input name="title" type="text" value="" />
        </label>
        <label class="workspace-field">
          <span>Phase</span>
          <select name="phase_id">
            <option value="">Bitte wählen</option>
            {#each modularPhases() as phase}
              <option value={phase.id} selected={selectedPhaseId() === phase.id}>
                {phase.title}
              </option>
            {/each}
          </select>
        </label>
        {#if form?.createModule?.error}
          <p class="workspace-note workspace-note--error">{form.createModule.error}</p>
        {/if}
        <div class="dialog-card__actions">
          <button class="workspace-link-action" type="submit">Anlegen</button>
        </div>
      </form>
    </div>
  </div>
{/if}
