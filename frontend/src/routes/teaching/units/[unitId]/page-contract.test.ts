import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("teacher unit graph route contract", () => {
  function routeSource(): string {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    return readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
  }

  it("uses shared workspace controls and no longer depends on legacy app.css popover styles", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const source = routeSource();
    const graphNodeSource = readFileSync(
      path.resolve(currentDir, "../../../../lib/components/teacher-unit-graph/GraphUnitNode.svelte"),
      "utf8"
    );
    const appCss = readFileSync(path.resolve(currentDir, "../../../../lib/styles/app.css"), "utf8");

    expect(source).toContain("<GraphInspectorPanel");
    expect(source).toContain('class="workspace-unit-commandbar-popover"');
    expect(source).toContain('class="workspace-field"');
    expect(graphNodeSource).toContain('class="teacher-flow-unit-node__quickedit-field workspace-field"');
    expect(appCss).not.toContain(".workspace-unit-commandbar-popover {");
    expect(appCss).not.toContain(".teacher-flow-unit-node__quickedit {");
  });

  it("keeps create dialogs in local state instead of using non-reactive browser URL state", () => {
    const source = routeSource();

    expect(source).toContain("let createPhaseOpen = $state");
    expect(source).toContain("let createModuleOpen = $state");
    expect(source).toContain("let createSectionOpen = $state");
    expect(source).toContain("function openCreateModuleDialog");
    expect(source).toContain("function closeCreateModuleDialog");
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

  it("updates successful graph action workspaces through route data and resets the SvelteFlow viewport once", () => {
    const source = routeSource();

    expect(source).toContain("workspaceForBuild: TeacherUnitWorkspaceView = workspaceState");
    expect(source).toContain("buildTeacherUnitFlow(workspaceForBuild, selection)");
    expect(source).toContain("const nextWorkspace = plainWorkspace(data.workspace)");
    expect(source).toContain("workspaceState = nextWorkspace");
    expect(source).toContain("function scheduleFlowRebuild");
    expect(source).toContain("queueMicrotask(() => {\n      void rebuildFlow(selection, workspaceForBuild);");
    expect(source).toContain("scheduleFlowRebuild(selection);");
    expect(source).not.toContain("function initialLastAppliedLoadWorkspace");
    expect(source).not.toContain("lastAppliedLoadWorkspace");
    expect(source).not.toContain("applyWorkspaceUpdate");
    expect(source).toContain("let flowBuildSequence = 0");
    expect(source).toContain("let flowViewport = $state");
    expect(source).toContain("let pendingViewportReset = false");
    expect(source).toContain("let handledForm: ActionData | undefined = undefined;");
    expect(source).not.toContain("let handledForm = $state");
    expect(source).toContain("const buildSequence = ++flowBuildSequence");
    expect(source).toContain("if (buildSequence !== flowBuildSequence)");
    expect(source).not.toContain("flowRenderKey");
    expect(source).not.toContain("scheduleFlowRebuild(data.workspace.selection, nextWorkspace);");
    expect(source).toContain("pendingViewportReset = true");
    expect(source).toContain("flowViewport = { x: 0, y: 0, zoom: 1 }");
    expect(source).toContain("pendingViewportReset = false");
    expect(source).not.toContain("flowCanvasGeneration");
    expect(source).not.toContain("{#key");
    expect(source).toContain("bind:viewport={flowViewport}");
    expect(source).not.toContain("formGraphActionSuccess");
  });

  it("uses route invalidation as the only graph mutation reconcile path", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const source = routeSource();
    const serverSource = readFileSync(path.resolve(currentDir, "+page.server.ts"), "utf8");
    const graphNodeSource = readFileSync(
      path.resolve(currentDir, "../../../../lib/components/teacher-unit-graph/GraphUnitNode.svelte"),
      "utf8"
    );
    const graphEdgeSource = readFileSync(
      path.resolve(currentDir, "../../../../lib/components/teacher-unit-graph/TeacherGraphEdge.svelte"),
      "utf8"
    );

    expect(source).toContain("import { applyAction, enhance } from \"$app/forms\";");
    expect(source).toContain("import { invalidateAll, replaceState } from \"$app/navigation\";");
    expect(source).toContain("await update({ reset: false });");
    expect(source).toContain("await invalidateAll();");
    expect(source).toContain("async function reloadWorkspace");
    expect(source).not.toContain("invalidateAll: false");
    expect(source).not.toContain("refreshWorkspaceView");
    expect(source).not.toContain("workspace: TeacherUnitWorkspaceView;");
    expect(source).not.toContain("success.workspace");

    expect(serverSource).not.toContain("async function loadWorkspace");
    expect(serverSource).not.toContain("workspace: await loadWorkspace");

    expect(graphNodeSource).not.toContain("const enhanceGraphForm");
    expect(graphNodeSource).toContain("use:enhance={data.enhanceGraphForm}");

    expect(graphEdgeSource).not.toContain("const enhanceGraphForm");
    expect(graphEdgeSource).toContain("use:enhance={data.enhanceGraphForm}");
  });

  it("handles action success URL patches exactly once through the enhance pipeline", () => {
    const source = routeSource();
    const syncUrlPatchCalls = source.match(/syncUrlPatch\(success\.next\)/g) ?? [];

    expect(syncUrlPatchCalls).toHaveLength(1);
    expect(source).toContain("const success = graphActionSuccessFromResult(result);");
    expect(source).toContain("closeCreateDialogsFromNext(success.next);");
    expect(source).toContain("await applyAction(result);");
    expect(source).toContain("await invalidateAll();");
    expect(source).toContain("return;");
    expect(source).not.toContain("if (success) {\n        if (success.message)");
    expect(source).not.toContain("if (success.next) {\n        syncUrlPatch(success.next);");
  });

  it("does not keep a second browser URL cache next to SvelteKit page state", () => {
    const source = routeSource();

    expect(source).not.toContain("let currentHref");
    expect(source).not.toContain("currentHref =");
    expect(source).toContain("function currentUrl(");
    expect(source).toContain("new URL(page.url)");
  });

  it("exposes edit and delete as direct design-system header actions", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const source = routeSource();
    const serverSource = readFileSync(path.resolve(currentDir, "+page.server.ts"), "utf8");

    expect(serverSource).toContain('showDeleteDialog: url.searchParams.get("delete") == "1"');
    expect(source).toContain('href={workspaceState.unit.edit_href}>Bearbeiten</a>');
    expect(source).toContain('href={pageHref({ delete: "1" })}>Löschen</a>');
    expect(source).not.toContain('aria-label="Einheitsaktionen"');
    expect(source).not.toContain('class="workspace-row-menu"');
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
