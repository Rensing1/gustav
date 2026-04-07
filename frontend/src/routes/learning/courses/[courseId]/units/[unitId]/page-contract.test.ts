import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("learning unit route contract", () => {
  it("uses the shared workspace settings menu instead of the local legacy layout menu", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const appCss = readFileSync(path.resolve(currentDir, "../../../../../../lib/styles/app.css"), "utf8");

    expect(routeSource).toContain('import WorkspaceSettingsMenu from "$lib/components/ui/WorkspaceSettingsMenu.svelte";');
    expect(routeSource).toContain("<WorkspaceSettingsMenu");
    expect(routeSource).not.toContain("learning-unit-layout-menu");
    expect(appCss).not.toContain(".learning-unit-layout-menu");
  });

  it("keeps pane item lists intact while tracking a single inline submission focus", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    expect(routeSource).toContain("function setSubmissionWorkspace");
    expect(routeSource).toContain("left: paneId === \"left\" ? { itemKey, mode } : { itemKey: null, mode: null }");
    expect(routeSource).toContain("right: paneId === \"right\" ? { itemKey, mode } : { itemKey: null, mode: null }");
    expect(routeSource).not.toContain("focus.left.itemKey ? leftEntries.filter");
    expect(routeSource).not.toContain("focus.right.itemKey ? rightEntries.filter");
  });

  it("keeps feedback requests inline with local polling instead of a redirect-only flow", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const serverSource = readFileSync(path.resolve(currentDir, "+page.server.ts"), "utf8");

    expect(routeSource).toContain('import { applyAction } from "$app/forms";');
    expect(routeSource).toContain("async function pollFeedbackSubmission");
    expect(routeSource).toContain("function enhanceTaskForm");
    expect(routeSource).toContain("feedbackPendingTaskId");
    expect(routeSource).toContain("const fastPollAttempts = 30");
    expect(routeSource).toContain("pendingSubmissionIntent");
    expect(routeSource).toContain("Die Rückmeldung dauert länger als üblich ...");
    expect(routeSource).not.toContain("Die Rückmeldung ist noch nicht fertig. Bitte prüfe den Verlauf gleich erneut.");
    expect(serverSource).toContain("moduleIdOverride");
    expect(serverSource).toContain("feedbackRequestedTaskId");
    expect(serverSource).toContain('message: "feedback_pending"');
    expect(serverSource).toContain("/submissions/finalize");
    expect(serverSource).toContain('message: "submitted"');
    expect(routeSource).toContain("async function requestUploadIntent");
    expect(routeSource).toContain("async function uploadFileToStorage");
    expect(routeSource).toContain("crypto.subtle.digest(\"SHA-256\"");
    expect(routeSource).toContain("/upload-intents");
    expect(routeSource).toContain("async function submitUploadFeedback");
    expect(serverSource).not.toContain("const uploadResponse = await fetch(uploadUrl");
    expect(serverSource).not.toContain("/upload-intents");
    expect(serverSource).not.toContain("throw redirect(303");
  });

  it("tracks submission history per task instead of one global history payload for all cards", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const workspaceSource = readFileSync(
      path.resolve(currentDir, "../../../../../../lib/components/learning-unit/LearningUnitContentWorkspace.svelte"),
      "utf8"
    );

    expect(routeSource).toContain("let submissionHistoryByTask = $state.raw<Record<string, LearningSubmission[]>>({})");
    expect(routeSource).toContain("function historyForTask(taskId: string): LearningSubmission[]");
    expect(routeSource).not.toContain("let historyState = $state<LearningSubmission[]>(data.history)");
    expect(workspaceSource).toContain("historyByTask");
    expect(workspaceSource).toContain("history={historyByTask[entry.item.task.id] ?? []}");
    expect(workspaceSource).not.toContain("{history}");
  });

  it("restores open modular tabs through an explicit restore flow with overview fallback", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    expect(routeSource).toContain("type ModularRestoreState = \"idle\" | \"restoring\" | \"ready\" | \"failed\"");
    expect(routeSource).toContain("let modularRestoreState = $state<ModularRestoreState>(\"idle\")");
    expect(routeSource).toContain("async function restoreOpenModules");
    expect(routeSource).toContain("Promise.race([restorePromise, timeoutPromise])");
    expect(routeSource).toContain("modularRestoreState = \"failed\"");
    expect(routeSource).toContain("view: \"overview\"");
    expect(routeSource).not.toContain("if (!isModularUnit() || !workspaceReady || !modularWorkspace.openTabs.length)");
    expect(routeSource).not.toContain("for (const moduleId of modularWorkspace.openTabs)");
  });
});
