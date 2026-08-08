import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("teacher unit graph route contract", () => {
  function routeSource(): string {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    return readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
  }

  it("uses one shared structure inspector and no embedded module quick editor", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const source = routeSource();
    const graphNodeSource = readFileSync(
      path.resolve(currentDir, "../../../../lib/components/teacher-unit-graph/GraphUnitNode.svelte"),
      "utf8"
    );
    const appCss = readFileSync(path.resolve(currentDir, "../../../../lib/styles/app.css"), "utf8");
    const teachingCss = readFileSync(
      path.resolve(currentDir, "../../../../lib/styles/teaching-workspace.css"),
      "utf8"
    );
    const viewportControlsSource = readFileSync(
      path.resolve(currentDir, "../../../../lib/components/teacher-unit-graph/TeacherGraphViewportControls.svelte"),
      "utf8"
    );

    expect(source).toContain("<GraphInspectorPanel");
    expect(source).toContain('class="workspace-unit-commandbar-popover"');
    expect(source).toContain('class="workspace-field"');
    expect(source).toContain("<GraphDeleteDialog");
    expect(source).toContain("GraphSelectionBar");
    expect(source).toContain('type StructurePanelMode = "create-phase" | "create-module" | "phase-properties" | "module-properties" | null');
    expect(graphNodeSource).not.toContain("teacher-flow-unit-node__quickedit");
    expect(appCss).not.toContain(".workspace-unit-commandbar-popover {");
    expect(appCss).not.toContain(".teacher-flow-unit-node__quickedit {");
    expect(teachingCss).toContain("pointer-events: none !important;");
    expect(teachingCss).toContain("z-index: 1 !important;");
    expect(teachingCss).toMatch(/\.teacher-flow-workspace__canvas\s*\{[^}]*overflow:\s*clip;/s);
    expect(viewportControlsSource).toContain('const phaseBands = allNodes.filter((node) => node.type === "phaseBand")');
    expect(viewportControlsSource).toContain("nodes: phaseBands.length > 0 ? phaseBands : allNodes");
  });

  it("keeps exactly one modular inspector mode in reactive local state", () => {
    const source = routeSource();

    expect(source).toContain("let structurePanelMode = $state<StructurePanelMode>(null)");
    expect(source).toContain("let createSectionOpen = $state");
    expect(source).toContain("function setStructurePanelMode");
    expect(source).toContain("function openCreateModuleDialog");
    expect(source).toContain("function setSelectionAndPanel");
    expect(source).toContain('searchParams.get("panel")');
    expect(source).toContain('nodesFocusable={true}');
    expect(source).toContain('elementsSelectable={true}');
    expect(source).toContain('.svelte-flow__node[data-id=');
    expect(source).not.toContain("let createPhaseOpen");
    expect(source).not.toContain("let createModuleOpen");
    expect(source).not.toContain("window.location.href");
    expect(source).not.toContain("window.history.replaceState");
  });

  it("renders linear section creation in the commandbar popover instead of the legacy dialog shell", () => {
    const source = routeSource();

    expect(source).toContain('role="dialog" aria-label="Abschnitt hinzufügen"');
    expect(source).toContain('class="workspace-unit-commandbar-popover"');
    expect(source).toContain('action="?/createSection"');
    expect(source).not.toContain('{#if showCreateSectionDialog()}\n  <div class="dialog-backdrop">');
  });

  it("updates successful graph actions through route data without resetting the current viewport", () => {
    const source = routeSource();

    expect(source).toContain("workspaceForBuild: TeacherUnitWorkspaceView = workspaceState");
    expect(source).toContain("buildTeacherUnitFlow(workspaceForBuild, selection)");
    expect(source).toContain('from "$lib/teacher-unit-workspace/view-state"');
    expect(source).toContain("const nextWorkspace = cloneWorkspace(data.workspace)");
    expect(source).toContain("workspaceState = nextWorkspace");
    expect(source).toContain("function scheduleFlowRebuild");
    expect(source).toContain("queueMicrotask(() => {\n      void rebuildFlow(selection, workspaceForBuild);");
    expect(source).toContain("scheduleFlowRebuild(selection);");
    expect(source).not.toContain("function initialLastAppliedLoadWorkspace");
    expect(source).not.toContain("lastAppliedLoadWorkspace");
    expect(source).not.toContain("applyWorkspaceUpdate");
    expect(source).toContain("let flowBuildSequence = 0");
    expect(source).toContain("let flowViewport = $state");
    expect(source).not.toContain("pendingViewportReset");
    expect(source).toContain("let handledForm: ActionData | undefined = undefined;");
    expect(source).not.toContain("let handledForm = $state");
    expect(source).toContain("const buildSequence = ++flowBuildSequence");
    expect(source).toContain("if (buildSequence !== flowBuildSequence)");
    expect(source).not.toContain("flowRenderKey");
    expect(source).not.toContain("scheduleFlowRebuild(data.workspace.selection, nextWorkspace);");
    expect(source).not.toContain("flowViewport = { x: 0, y: 0, zoom: 1 }");
    expect(source).not.toContain("flowCanvasGeneration");
    expect(source).not.toContain("{#key");
    expect(source).toContain("bind:viewport={flowViewport}");
    expect(source).not.toContain("formGraphActionSuccess");
  });

  it("uses route invalidation as the only graph mutation reconcile path", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const source = routeSource();
    const serverSource = readFileSync(path.resolve(currentDir, "+page.server.ts"), "utf8");
    const deleteDialogSource = readFileSync(
      path.resolve(currentDir, "../../../../lib/components/teacher-unit-graph/GraphDeleteDialog.svelte"),
      "utf8"
    );
    const graphNodeSource = readFileSync(
      path.resolve(currentDir, "../../../../lib/components/teacher-unit-graph/GraphUnitNode.svelte"),
      "utf8"
    );
    const graphEdgeSource = readFileSync(
      path.resolve(currentDir, "../../../../lib/components/teacher-unit-graph/TeacherGraphEdge.svelte"),
      "utf8"
    );

    expect(source).toContain("import { enhance } from \"$app/forms\";");
    expect(source).toContain("import { goto, invalidateAll, pushState, replaceState } from \"$app/navigation\";");
    expect(source).toContain("await update({ reset: false });");
    expect(source).toContain("await invalidateAll();");
    expect(source).toContain("await update({ reset: true, invalidateAll: false });");
    expect(source).toContain("await goto(targetHref");
    expect(source).toContain("invalidateAll: true");
    expect(source).toContain("async function reloadWorkspace");
    expect(source).not.toContain("refreshWorkspaceView");
    expect(source).not.toContain("workspace: TeacherUnitWorkspaceView;");
    expect(source).not.toContain("success.workspace");

    expect(serverSource).not.toContain("async function loadWorkspace");
    expect(serverSource).not.toContain("workspace: await loadWorkspace");

    expect(graphNodeSource).not.toContain("enhanceGraphForm");
    expect(graphNodeSource).not.toContain("use:enhance");

    expect(graphEdgeSource).not.toContain("const enhanceGraphForm");
    expect(graphEdgeSource).toContain("use:enhance={data.enhanceGraphForm}");
  });

  it("positions new phases contextually and requires explicit destructive confirmation", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const source = routeSource();
    const serverSource = readFileSync(path.resolve(currentDir, "+page.server.ts"), "utf8");
    const deleteDialogSource = readFileSync(
      path.resolve(currentDir, "../../../../lib/components/teacher-unit-graph/GraphDeleteDialog.svelte"),
      "utf8"
    );

    expect(source).toContain('name="after_phase_id"');
    expect(serverSource).toContain("after_phase_id: afterPhaseId || null");
    expect(serverSource).toContain('formData.get("confirmed")');
    expect(serverSource).toContain('confirmed !== "1"');
    expect(deleteDialogSource).toContain('`${entityLabel} und Inhalte löschen`');
    expect(source).toContain("Modul löschen");
  });

  it("keeps browser graph 401 responses recoverable instead of mapping them to graph errors", () => {
    const source = routeSource();

    expect(source).toContain('import { handleBrowserAuthRecovery } from "$lib/utils/browser-auth-recovery";');
    expect(source).toContain("if (handleBrowserAuthRecovery(response))");
    expect(source).toContain('throw new Error("auth_recovery_started");');
    expect(source).toContain('if (detail === "auth_recovery_started")');
    expect(source).toContain("return;");
  });

  it("handles action success URL patches exactly once through the enhance pipeline", () => {
    const source = routeSource();
    const targetHrefCalls = source.match(/success\.next \? pageHref\(success\.next\) : null/g) ?? [];

    expect(targetHrefCalls).toHaveLength(1);
    expect(source).toContain("const success = graphActionSuccessFromResult(result);");
    expect(source).toContain("closeCreateDialogsFromNext(success.next);");
    expect(source).toContain("await update({ reset: true, invalidateAll: false });");
    expect(source).toContain("await goto(targetHref");
    expect(source).toContain("return;");
    expect(source).not.toContain("if (success) {\n        if (success.message)");
    expect(source).not.toContain("syncUrlPatch(success.next)");
  });

  it("does not keep a second browser URL cache next to SvelteKit page state", () => {
    const source = routeSource();

    expect(source).not.toContain("let currentHref");
    expect(source).not.toContain("lastRouteStateKey");
    expect(source).not.toContain("currentHref =");
    expect(source).toContain("function currentUrl(");
    expect(source).toContain("new URL(document.location.href)");
    expect(source).toContain("new URL(page.url.href)");
    expect(source).toContain("function handleWindowPopState");
    expect(source).toContain("onpopstate={handleWindowPopState}");
    expect(source).toContain("onMount(() => applyRouteState(currentUrl()))");
  });

  it("exposes explicit unit editing and keeps destructive deletion in the overflow menu", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const source = routeSource();
    const serverSource = readFileSync(path.resolve(currentDir, "+page.server.ts"), "utf8");

    expect(serverSource).toContain('showDeleteDialog: url.searchParams.get("delete") == "1"');
    expect(serverSource).toContain("wideWorkspaceShell: true");
    expect(source).toContain("Lerneinheit bearbeiten");
    expect(source).toContain('aria-label="Lerneinheitsaktionen"');
    expect(source).toContain('href={pageHref({ delete: "1" })}>Lerneinheit löschen</a>');
  });

  it("renders the unit delete dialog with exact-title confirmation and course warning", () => {
    const source = routeSource();

    expect(source).toContain("{#if data.showDeleteDialog}");
    expect(source).toContain('action="?/deleteUnit"');
    expect(source).toContain("Diese Lerneinheit ist");
    expect(source).toContain("Kurs");
    expect(source).toContain("Titel zur Bestätigung");
    expect(source).toContain("Lerneinheit endgültig löschen");
  });
});
