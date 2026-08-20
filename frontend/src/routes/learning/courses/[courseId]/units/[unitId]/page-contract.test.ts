import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { readWorkspaceCssBundle } from "$lib/styles/test-css-bundle";

describe("learning unit route contract", () => {
  it("uses the shared workspace settings menu instead of the local legacy layout menu", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const appCss = readWorkspaceCssBundle(path.resolve(currentDir, "../../../../../../lib/styles"));
    const designSystemCss = appCss;
    const designDoc = readFileSync(path.resolve(currentDir, "../../../../../../../../docs/DESIGN.md"), "utf8");

    expect(routeSource).toContain('import WorkspaceSettingsMenu from "$lib/components/ui/WorkspaceSettingsMenu.svelte";');
    expect(routeSource).toContain('import LearnerContentWorkspace from "$lib/components/learning-unit/LearnerContentWorkspace.svelte";');
    expect(routeSource).toContain("<WorkspaceSettingsMenu");
    expect(routeSource).toContain('class="learning-unit-toolbar__utility"');
    expect(routeSource).toContain('class="learning-unit-layout-frame learning-unit-layout-frame--toolbar"');
    expect(routeSource).toContain('learnerWorkspace.surface === "task" ? "working" : "orienting"');
    expect(routeSource).not.toContain('import ModeSwitch from "$lib/components/ui/ModeSwitch.svelte";');
    expect(routeSource).toContain("← Zum Lernpfad");
    expect(routeSource).not.toContain("showSplitToggle=");
    expect(routeSource).not.toContain("onToggleSplitView=");
    expect(routeSource).toContain("modularSettingsMenuOpen = !modularSettingsMenuOpen");
    expect(routeSource).toContain('!target.closest("[data-layout-menu-root]")');
    expect(routeSource).toContain('if (event.key === "Escape")');
    expect(routeSource).not.toContain('<div class="learning-unit-layout-rail">\n        <div class="learning-unit-layout-frame learning-unit-layout-frame--toolbar">');
    expect(routeSource).not.toContain("learning-unit-layout-menu");
    expect(appCss).not.toContain(".learning-unit-layout-menu");
    expect(designDoc).toContain("## 7. Form, Raum und Bewegung");
    expect(designDoc).toContain("### 7.1 Spacing");
    expect(designDoc).toContain("### 7.3 Flächen");
    expect(designDoc).toContain("### 11.3 Leseansicht und Inhalte");
    expect(designDoc).toContain("Lernraum-spezifische Overrides unter `.learning-unit-content-shell` gehören in");
    expect(designDoc).toContain("das aktive Lernraum-CSS-Bundle (`frontend/src/lib/styles/learning-unit.css`");
    expect(designSystemCss).toMatch(/\.learning-unit-content-shell \.workspace-outline\s*\{[^}]*position:\s*sticky;/s);
    expect(designSystemCss).not.toMatch(/\.learning-unit-content-shell \.workspace-outline\s*\{[^}]*background:\s*transparent;/s);
    expect(designSystemCss).not.toMatch(/\.learning-unit-content-shell \.workspace-outline\s*\{[^}]*border:\s*0;/s);
    expect(designSystemCss).not.toMatch(/\.learning-unit-content-shell \.workspace-outline\s*\{[^}]*box-shadow:\s*none;/s);
    expect(designSystemCss).not.toMatch(/\.workspace-outline__item--active::after\s*\{/s);
    expect(designSystemCss).not.toMatch(/\.workspace-outline__item--active \.workspace-outline__item-label\s*\{[^}]*color:\s*var\(--color-accent\);/s);
    expect(designSystemCss).toMatch(/\.learning-unit-content-shell \.learning-unit-workspace-surface\s*\{[^}]*padding:\s*0;[^}]*border:\s*0;[^}]*background:\s*transparent;[^}]*box-shadow:\s*none;/s);
    expect(designSystemCss).toMatch(/\.learning-unit-content-shell \.learning-work-item__toggle\s*\{[^}]*padding:\s*0\.45rem 0;/s);
    expect(designSystemCss).toMatch(
      /\.learning-unit-content-shell \.learning-work-item--material \.learning-work-item__toggle\s*\{[^}]*padding:\s*var\(--space-4\) var\(--space-5\) var\(--space-2\);/s
    );
    expect(designSystemCss).toMatch(
      /\.learning-unit-content-shell \.learning-work-item--material \.learning-work-item__title\s*\{[^}]*font-size:\s*calc\(1\.08rem \* var\(--learning-unit-font-scale\)\);[^}]*font-weight:\s*600;[^}]*line-height:\s*1\.18;/s
    );
    expect(appCss).toMatch(/\.learning-unit-toolbar__utility\s*\{[^}]*justify-content:\s*flex-end;[^}]*margin-left:\s*auto;/s);
    expect(appCss).toMatch(/\.learning-unit-layout-frame--toolbar\s*\{[^}]*width:\s*min\(100%,\s*var\(--learning-unit-workspace-width\)\);/s);
    expect(appCss).toMatch(/\.learning-unit-toolbar__utility \.workspace-top-action--quiet\s*\{[^}]*border-color:\s*color-mix\(in srgb,\s*var\(--color-border\) 38%,\s*transparent 62%\);/s);
  });

  it("uses one learner-scoped work state instead of exposing split-pane controls", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    expect(routeSource).toContain("let learnerWorkspace = $state<LearnerWorkspaceState>");
    expect(routeSource).toContain("async function beginTaskWorkspace");
    expect(routeSource).toContain("function leaveTaskWorkspace");
    expect(routeSource).toContain('window.scrollTo({ top: 0, behavior: "auto" })');
    expect(routeSource).toContain('document.getElementById("learner-task-back")?.focus');
    expect(routeSource).toContain("learnerWorkspaceStorageKeys(data.user?.sub ?? null");
    expect(routeSource).not.toContain("showSplitToggle=");
    expect(routeSource).not.toContain("onToggleSplitView=");
    expect(routeSource).not.toMatch(/\b(paneStacks|splitView|activePane)\b/);
    expect(routeSource).toContain('surface: "task"');
    expect(routeSource).toContain('surface: "reading"');
    expect(routeSource).toContain('surface: "graph"');
  });

  it("never exposes a tab-local task return action in the graph", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    expect(routeSource).toContain("learningPathState(learnerWorkspace)");
    expect(routeSource).not.toContain("function returnToActiveTask");
    expect(routeSource).not.toContain("learning-path-task-return");
    expect(routeSource).not.toContain("Entwurf geöffnet");
    expect(routeSource).not.toContain("Zurück zum Entwurf");
    expect(routeSource).not.toContain("Aufgabe wird weiterbearbeitet.");
  });

  it("passes the authenticated learner id to inline task draft persistence", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const workspaceSource = readFileSync(
      path.resolve(currentDir, "../../../../../../lib/components/learning-unit/LearnerContentWorkspace.svelte"),
      "utf8"
    );
    const taskCardSource = readFileSync(
      path.resolve(currentDir, "../../../../../../lib/components/learning-unit/LearningTaskCard.svelte"),
      "utf8"
    );

    expect(routeSource).toContain("learnerSub={data.user?.sub ?? null}");
    expect(workspaceSource).toContain("learnerSub");
    expect(workspaceSource).toContain("{learnerSub}");
    expect(taskCardSource).toContain("learnerSub");
  });

  it("clears only the finalized task draft after a successful enhanced form action", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    expect(routeSource).toContain('import { clearSubmissionDraft } from "$lib/learning-unit/submission-drafts";');
    expect(routeSource).toContain("taskId: payload.finalizedTaskId");
    expect(routeSource).toContain("clearSubmissionDraft(window.sessionStorage, draftScope)");
    expect(routeSource).toContain("clearSubmissionDraft(window.localStorage, draftScope)");
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
    expect(routeSource).toContain('import { prepareBrowserStorageUpload } from "$lib/utils/browser-storage-upload";');
    expect(routeSource).toContain('import { handleBrowserAuthRecovery } from "$lib/utils/browser-auth-recovery";');
    expect(routeSource).toContain("prepareBrowserStorageUpload({");
    expect(routeSource).toContain("onAuthRecovery: handleBrowserAuthRecovery");
    expect(routeSource).toContain("/upload-intents");
    expect(routeSource).toContain("async function submitUploadFeedback");
    expect(serverSource).not.toContain("const uploadResponse = await fetch(uploadUrl");
    expect(serverSource).not.toContain("/upload-intents");
    expect(serverSource).not.toContain("throw redirect(303");
  });

  it("tracks the exact final dialog submission until its feedback is ready", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    expect(routeSource).toContain("async function handleProgressPersisted(taskId: string, submission?: LearningSubmission | null)");
    expect(routeSource).toContain("if (submission)");
    expect(routeSource).toContain('void pollFeedbackSubmission(taskId, submission.id, "submit", "Rückmeldung ist bereit")');
    expect(routeSource).not.toContain("const activeTaskId = learnerWorkspace.activeTask?.taskId ?? null");
  });

  it("starts final submissions visibly and cancels duplicate form requests", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    expect(routeSource).toContain('import { beginSubmissionAttempt } from "$lib/learning-unit/submission-finalization";');
    expect(routeSource).toContain("const attempt = beginSubmissionAttempt(feedbackPendingTaskId, taskId, intent)");
    expect(routeSource).toMatch(/if \(!attempt\.accepted\) \{\s*setClientSubmissionError\(taskId, attempt\.statusMessage\);\s*cancel\(\);/);
    expect(routeSource).toContain("feedbackPendingTaskId = attempt.taskId");
    expect(routeSource).toContain("feedbackStatusMessage = attempt.statusMessage");
  });

  it("restores a directly linked task before unrelated saved modules", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    expect(routeSource).toContain("const directTaskRequested = Boolean(data.requestedTaskId && data.activeModule)");
    expect(routeSource).toContain("void restoreOpenModulesInBackground(seeded.openTabs)");
  });

  it("does not repeatedly reapply the same result state after an enhanced form action", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    expect(routeSource).toContain("requestedTaskId === actionTaskId()");
    expect(routeSource).not.toContain("if (!workspaceReady || !actionTaskId())");
  });

  it("applies server-provided history without subscribing to state changed by the history helper", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    expect(routeSource).toContain('import { onMount, tick, untrack } from "svelte";');
    expect(routeSource).toMatch(/\$effect\(\(\) => \{\s*const historyTaskId = data\.historyTaskId;[\s\S]*?untrack\(\(\) => \{[\s\S]*?setTaskHistory\(historyTaskId, history\)/);
  });

  it("shows a clear message when uploaded bytes do not match the expected content type", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    expect(routeSource).toContain('reason === "invalid_upload_content"');
    expect(routeSource).toContain("Die Datei passt nicht zum erwarteten Dateityp. Bitte wähle die richtige Datei aus.");
  });

  it("tracks submission history per task instead of one global history payload for all cards", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const workspaceSource = readFileSync(
      path.resolve(currentDir, "../../../../../../lib/components/learning-unit/LearnerContentWorkspace.svelte"),
      "utf8"
    );
    const taskCardSource = readFileSync(
      path.resolve(currentDir, "../../../../../../lib/components/learning-unit/LearningTaskCard.svelte"),
      "utf8"
    );

    expect(routeSource).toContain("let submissionHistoryByTask = $state.raw<Record<string, LearningSubmission[]>>({})");
    expect(routeSource).toContain("function historyForTask(taskId: string): LearningSubmission[]");
    expect(routeSource).not.toContain("let historyState = $state<LearningSubmission[]>(data.history)");
    expect(workspaceSource).toContain("historyByTask");
    expect(workspaceSource).toContain("history={taskHistory(task.id)}");
    expect(workspaceSource).toContain("compactLayout={true}");
    expect(workspaceSource).toContain('class="learner-orientation__module"');
    expect(workspaceSource).toContain('class="learner-orientation__materials"');
    expect(workspaceSource).toContain('class="learner-orientation__tasks"');
    expect(workspaceSource).toContain("moduleMeta(group)");
    expect(workspaceSource).toContain('class="learner-task-workbench"');
    expect(workspaceSource).toContain('workspaceOnly={true}');
    expect(taskCardSource).toContain("learning-task-row__preview");
    expect(taskCardSource).toContain("taskPreview().text");
    expect(taskCardSource).toContain("taskPreview().truncated");
    expect(taskCardSource).toContain("return `${taskTitle} beginnen`;");
    expect(taskCardSource).not.toContain("compactStatusLabel()");
    expect(workspaceSource).not.toContain("{history}");
  });

  it("keeps review history reloads recoverable instead of treating empty local state as missing feedback", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const navigationSource = readFileSync(
      path.resolve(currentDir, "../../../../../../lib/learning-unit/learner-navigation.ts"),
      "utf8"
    );

    expect(routeSource).toContain('type SubmissionHistoryLoadState = "not_loaded" | "loading" | "loaded" | "failed" | "unavailable"');
    expect(routeSource).toContain("let submissionHistoryStateByTask = $state.raw<Record<string, SubmissionHistoryLoadState>>({})");
    expect(routeSource).toContain("function setTaskHistoryState(taskId: string, state: SubmissionHistoryLoadState)");
    expect(routeSource).toContain("async function ensureSubmissionHistoryLoaded(taskId: string)");
    expect(routeSource).toContain("handleRecoverableAuthResponse(response)");
    expect(routeSource).toContain("return handleBrowserAuthRecovery(response)");
    expect(routeSource).not.toContain('window.location.assign(`/auth/continue?redirect=${encodeURIComponent(redirectPath)}`)');
    expect(routeSource).toContain("feedbackStatusMessage = \"Die Abgabe wird geladen ...\";");
    expect(routeSource).not.toContain("feedbackStatusMessage = \"Die Abgabe konnte nicht geladen werden.\";");
    expect(navigationSource).toContain('"history"');
    expect(navigationSource).toContain("next.searchParams.delete(key)");
    expect(routeSource).not.toContain("const currentHistoryTaskId = next.searchParams.get(\"history\")");
  });

  it("guards submission-history requests before building course and task URLs", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    expect(routeSource).toContain('import { buildLearningSubmissionHistoryUrl, MISSING_SUBMISSION_HISTORY_CONTEXT_MESSAGE } from "$lib/utils/learning-submission-history-url";');
    expect(routeSource).toContain("const historyUrl = buildLearningSubmissionHistoryUrl(data.courseId, taskId);");
    expect(routeSource).toContain('throw new Error("history_missing_context");');
    expect(routeSource).toContain('if (reason === "history_missing_context")');
    expect(routeSource).toContain("feedbackStatusMessage = MISSING_SUBMISSION_HISTORY_CONTEXT_MESSAGE;");
    expect(routeSource).not.toContain("`/api/learning/courses/${encodeURIComponent(data.courseId)}/tasks/${encodeURIComponent(taskId)}/submissions?limit=10&offset=0`");
  });

  it("derives task context from opened modules without a parallel pin store", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const workspaceSource = readFileSync(
      path.resolve(currentDir, "../../../../../../lib/components/learning-unit/LearnerContentWorkspace.svelte"),
      "utf8"
    );

    expect(routeSource).toContain("orderedOpenModulesForContent()");
    expect(routeSource).toContain("closable: module.id !== activeModuleId");
    expect(routeSource).not.toContain("manualReferences");
    expect(routeSource).not.toContain("ensureContextReferenceSourceLoaded");
    expect(routeSource).not.toContain("addContextReference");
    expect(workspaceSource).toContain("<LearnerMaterialContext");
    expect(workspaceSource).not.toContain("Material suchen");
    expect(workspaceSource).not.toContain("Angeheftet");
  });

  it("keeps the active task mounted while selecting another module in the graph", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    expect(routeSource).toContain('const selectingContext = learnerWorkspace.surface === "graph" && Boolean(learnerWorkspace.activeTask);');
    expect(routeSource).toContain("activeTask: learnerWorkspace.activeTask");
    expect(routeSource).toContain('compactSurface: "materials"');
    expect(routeSource).toContain("focusedModuleId: moduleId");
    expect(routeSource).toContain('hidden={learnerWorkspace.surface === "graph"}');
  });

  it("handles direct browser fetch 401 responses through shared auth recovery before domain errors", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    const recoveryChecks = routeSource.match(/handleRecoverableAuthResponse\(response\)/g) ?? [];
    expect(recoveryChecks.length).toBeGreaterThanOrEqual(4);
    expect(routeSource).toContain('throw new Error("auth_recovery_started")');
    expect(routeSource).toContain('if (reason === "auth_recovery_started")');
  });

  it("stores only explicitly collapsed reading materials", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    expect(routeSource).toContain("function toggleReadingMaterial");
    expect(routeSource).toContain("learnerWorkspace.collapsedItemKeys.includes(itemKey)");
    expect(routeSource).not.toContain("reopenMaterialEntries");
  });

  it("derives modular spacing from DESIGN.md instead of flattening modules into one continuous list", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const appCss = readWorkspaceCssBundle(path.resolve(currentDir, "../../../../../../lib/styles"));
    const designSystemCss = appCss;
    const designDoc = readFileSync(path.resolve(currentDir, "../../../../../../../../docs/DESIGN.md"), "utf8");

    expect(designDoc).toContain("- `--space-4`: `1rem`");
    expect(designDoc).toContain("- `--space-5`: `1.5rem`");
    expect(designDoc).toContain("- `--space-6`: `2rem`");
    expect(designDoc).toContain("- `--space-7`: `3rem`");
    expect(appCss).toMatch(/\.learning-unit-pane__stack--modules\s*\{[^}]*gap:\s*var\(--space-7\);/s);
    expect(designSystemCss).toMatch(
      /\.learning-unit-content-shell \.learning-unit-pane__stack:not\(\.learning-unit-pane__stack--modules\)\s*\{[^}]*gap:\s*0;/s
    );
    expect(designSystemCss).not.toMatch(/\.learning-unit-content-shell \.learning-unit-pane__stack\s*\{[^}]*gap:\s*0;/s);
    expect(appCss).toMatch(/\.learning-unit-module\s*\{[^}]*gap:\s*var\(--space-5\);/s);
    expect(appCss).toMatch(/\.learning-unit-module__materials,\s*\.learning-unit-module__tasks\s*\{[^}]*gap:\s*var\(--space-4\);/s);
    expect(appCss).toMatch(/\.learning-unit-module__tasks\s*\{[^}]*margin-top:\s*var\(--space-6\);/s);
    expect(appCss).toMatch(
      /\.learning-unit-module__index\s*\{[^}]*font-family:\s*var\(--font-technical\);[^}]*text-transform:\s*uppercase;/s
    );
    expect(designDoc).toContain("Der Modultitel ist der klare Einstiegspunkt eines Moduls");
    expect(designDoc).toContain("`MATERIALIEN` und `AUFGABEN` bleiben technische Marker");
    expect(designDoc).toContain("Zwei Zeilen für lange Modultitel sind erlaubt");
    expect(designDoc).toContain("Der Abstand vom Modulkopf zum ersten Abschnitt ist größer");
    expect(designSystemCss).toMatch(
      /\.learning-unit-content-shell \.learning-unit-module__title\s*\{[^}]*color:\s*var\(--color-link\);[^}]*font-size:\s*calc\(1\.56rem \* var\(--learning-unit-headline-scale\)\);[^}]*line-height:\s*1\.06;[^}]*display:\s*-webkit-box;[^}]*-webkit-line-clamp:\s*2;/s
    );
    expect(designSystemCss).toMatch(
      /\.learning-unit-content-shell \.learning-unit-pane-grid--split \.learning-unit-module__title\s*\{[^}]*font-size:\s*calc\(1\.34rem \* var\(--learning-unit-headline-scale\)\);/s
    );
    expect(designSystemCss).toMatch(
      /\.learning-unit-content-shell \.learning-unit-module__meta\s*\{[^}]*font-family:\s*var\(--font-technical\);[^}]*font-size:\s*calc\(0\.78rem \* var\(--learning-unit-label-scale\)\);/s
    );
    expect(designSystemCss).toMatch(
      /\.learning-unit-content-shell \.learning-unit-module__section-head h5\s*\{[^}]*color:\s*color-mix\(in srgb,\s*var\(--color-text\) 78%,\s*transparent 22%\);[^}]*font-family:\s*var\(--font-technical\);[^}]*font-size:\s*calc\(0\.82rem \* var\(--learning-unit-label-scale\)\);[^}]*font-weight:\s*700;[^}]*letter-spacing:\s*0\.14em;/s
    );
    expect(designSystemCss).toMatch(
      /\.learning-unit-content-shell \.learning-unit-module__header\s*\{[^}]*margin-bottom:\s*var\(--space-6\);/s
    );
    expect(designSystemCss).toMatch(
      /\.learning-unit-content-shell \.learning-unit-module__section-head\s*\{[^}]*margin-bottom:\s*var\(--space-2\);/s
    );
    expect(appCss).toMatch(
      /\.learning-task-row\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+auto;/s
    );
    expect(appCss).toMatch(/\.learning-task-row__preview\s*\{[^}]*-webkit-line-clamp:\s*2;[^}]*white-space:\s*normal;[^}]*text-overflow:\s*ellipsis;/s);
    expect(designDoc).toContain("kompakte Task-Zeilen im modularen Lernraum nutzen eine Vorschauzeile");
    expect(designDoc).toContain("Status wird primär über Balken und Tönung getragen");
    expect(designDoc).toContain("Die vollständige Aufgabenstellung erscheint in der aktiven Detailansicht inline");
    expect(designDoc).toContain("Die Aufgabenbearbeitung ist ein eigener Fokusraum");
    expect(designDoc).toContain("`accent` für Primäraktionen");
    expect(designDoc).toContain("`quiet` für normale Sekundäraktionen");
    expect(designDoc).toContain("`subtle` für kleine, nicht-dominante Nebenaktionen");
    expect(designSystemCss).toMatch(/\.workspace-top-action--subtle,\s*\.workspace-link-action--subtle\s*\{[^}]*min-height:\s*1\.72rem;/s);
    expect(designSystemCss).toMatch(/\.workspace-top-action--subtle,\s*\.workspace-link-action--subtle\s*\{[^}]*box-shadow:\s*1px 1px 0/s);
  });

  it("uses one subtle card per module while keeping the pane surface itself cardless", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const appCss = readWorkspaceCssBundle(path.resolve(currentDir, "../../../../../../lib/styles"));
    const designSystemCss = appCss;
    const designDoc = readFileSync(path.resolve(currentDir, "../../../../../../../../docs/DESIGN.md"), "utf8");

    expect(designDoc).toContain("### 7.3 Flächen");
    expect(designDoc).toContain("### 11.3 Leseansicht und Inhalte");
    expect(designDoc).toContain("## 13. Verbotene Alt-Muster");
    expect(designSystemCss).toMatch(/\.learning-unit-content-shell \.learning-unit-workspace-surface\s*\{[^}]*padding:\s*0;[^}]*border:\s*0;[^}]*background:\s*transparent;[^}]*box-shadow:\s*none;/s);
    expect(designSystemCss).toMatch(
      /\.learning-unit-content-shell \.workspace-outline\s*\{[^}]*border:\s*1px solid color-mix\(in srgb,\s*var\(--color-border\) 72%,\s*white 28%\);[^}]*background:\s*var\(--color-bg-surface\);[^}]*box-shadow:\s*2px 2px 0 color-mix\(in srgb,\s*var\(--color-border\) 10%,\s*transparent 90%\);/s
    );
    expect(appCss).toMatch(
      /\.learning-unit-module\s*\{[^}]*padding:\s*var\(--space-5\);[^}]*background:\s*var\(--color-bg-surface\);[^}]*border:\s*1px solid color-mix\(in srgb,\s*var\(--color-border\) 72%,\s*white 28%\);[^}]*box-shadow:\s*2px 2px 0 color-mix\(in srgb,\s*var\(--color-border\) 10%,\s*transparent 90%\);/s
    );
    expect(appCss).toMatch(
      /\.learning-work-item--material\s*\{[^}]*background:\s*var\(--color-bg-surface\);[^}]*border:\s*1px solid color-mix\(in srgb,\s*var\(--color-border\) 72%,\s*white 28%\);[^}]*box-shadow:\s*2px 2px 0 color-mix\(in srgb,\s*var\(--color-border\) 10%,\s*transparent 90%\);/s
    );
    expect(appCss).toMatch(
      /\.learning-unit-pane-grid--split \.learning-unit-module\s*\{[^}]*gap:\s*var\(--space-4\);[^}]*padding:\s*var\(--space-4\);/s
    );
  });

  it("documents and styles learner markdown as a shared GFM-capable surface", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const packageJson = readFileSync(path.resolve(currentDir, "../../../../../../../../frontend/package.json"), "utf8");
    const markdownSource = readFileSync(path.resolve(currentDir, "../../../../../../lib/utils/markdown.ts"), "utf8");
    const appCss = readWorkspaceCssBundle(path.resolve(currentDir, "../../../../../../lib/styles"));
    const designDoc = readFileSync(path.resolve(currentDir, "../../../../../../../../docs/DESIGN.md"), "utf8");

    expect(packageJson).toContain('"markdown-it"');
    expect(packageJson).toContain('"isomorphic-dompurify"');
    expect(markdownSource).toContain("MarkdownIt");
    expect(markdownSource).toContain("DOMPurify");
    expect(markdownSource).toContain("ALLOWED_TAGS");
    expect(markdownSource).toContain('"br"');
    expect(markdownSource).toContain("linkify: true");
    expect(markdownSource).toContain("breaks: true");
    expect(appCss).toMatch(/\.markdown-prose table\s*\{[^}]*width:\s*100%;[^}]*border-collapse:\s*collapse;/s);
    expect(appCss).toMatch(/\.markdown-prose th,\s*\.markdown-prose td\s*\{[^}]*border:\s*1px solid/s);
    expect(appCss).toMatch(/\.markdown-prose a\s*\{[^}]*color:\s*var\(--color-link\);/s);
    expect(designDoc).toContain("Markdown im Schüler-Lernraum wird zentral");
    expect(designDoc).toContain("nummerierte Listen, Links, Tabellen, `<br>`");
  });

  it("uses the same bounded content grid as the application header", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const workspaceSource = readFileSync(
      path.resolve(currentDir, "../../../../../../lib/components/learning-unit/LearnerContentWorkspace.svelte"),
      "utf8"
    );
    const appCss = readWorkspaceCssBundle(path.resolve(currentDir, "../../../../../../lib/styles"));
    const designDoc = readFileSync(path.resolve(currentDir, "../../../../../../../../docs/DESIGN.md"), "utf8");

    expect(designDoc).toContain("### 7.1 Spacing");
    expect(designDoc).toContain("### 11.3 Leseansicht und Inhalte");
    expect(appCss).not.toMatch(/\.learning-unit-pane-grid--single\s*\{[^}]*48rem/s);
    expect(appCss).not.toMatch(/\.learning-unit-space\.workspace-page--learner-unit-content\s*\{[^}]*100vw/s);
    expect(appCss).not.toMatch(/\.learning-unit-space\s*\{[^}]*--learning-unit-workspace-width:\s*112rem/s);
    expect(appCss).toMatch(/\.learning-unit-layout-frame\s*\{[^}]*width:\s*min\(100%,\s*var\(--layout-content-max\)\);/s);
    expect(routeSource).toContain('class="learning-unit-layout-rail"');
    expect(routeSource).toContain('class="learning-unit-layout-frame"');
    expect(workspaceSource).not.toContain('class="learning-unit-layout-rail"');
    expect(workspaceSource).not.toContain('class="learning-unit-layout-frame"');
  });

  it("removes horizontal page separators while keeping task rows as the primary objects", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const appCss = readWorkspaceCssBundle(path.resolve(currentDir, "../../../../../../lib/styles"));
    const designDoc = readFileSync(path.resolve(currentDir, "../../../../../../../../docs/DESIGN.md"), "utf8");

    expect(designDoc).toContain("### 7.3 Flächen");
    expect(designDoc).toContain("## 13. Verbotene Alt-Muster");
    expect(appCss).not.toMatch(/\.learning-unit-module\s*\{[^}]*border-bottom:/s);
    expect(appCss).not.toMatch(/\.learning-unit-module__section-head\s*\{[^}]*border-bottom:/s);
    expect(appCss).toMatch(/\.learning-work-item__body\s*\{[^}]*display:\s*grid;[^}]*padding:\s*0\.95rem 0 1\.1rem;[^}]*\}/s);
    expect(appCss).not.toMatch(/\.learning-task-status\s*\{[^}]*border-top:/s);
    expect(appCss).not.toMatch(/\.learning-task-submission-summary\s*\{[^}]*border-top:/s);
    expect(appCss).toMatch(/\.learning-task-row\s*\{[^}]*border:\s*1px solid/s);
    expect(appCss).toMatch(
      /\.learning-unit-module__section-body\s*>\s*\.learning-work-item:last-child,\s*\.learning-unit-module__section-body\s*>\s*\.learning-task-workspace:last-child\s*\{[^}]*border-bottom:\s*0;[^}]*padding-bottom:\s*0;/s
    );
  });

  it("restores open modular tabs through an explicit restore flow with overview fallback", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    expect(routeSource).toContain("type ModularRestoreState = \"idle\" | \"restoring\" | \"ready\" | \"failed\"");
    expect(routeSource).toContain("let modularRestoreState = $state<ModularRestoreState>(\"idle\")");
    expect(routeSource).toContain("async function restoreOpenModules");
    expect(routeSource).toContain("Promise.race([restorePromise, timeoutPromise])");
    expect(routeSource).toContain("modularRestoreState = \"failed\"");
    expect(routeSource).toContain("graphState = data.graph ? plainGraph(data.graph) : null;");
    expect(routeSource).toContain("modularRestoreMessage = \"Die Inhalte konnten nicht vollständig wiederhergestellt werden. Du kannst die Module im Lernpfad erneut öffnen.\"");
    expect(routeSource).toContain('{ surface: "graph", moduleId: null, taskId: null, panel: null }');
    expect(routeSource).not.toContain("view: \"overview\",\n        submissionFocus: emptySubmissionFocus()");
    expect(routeSource).not.toContain("if (!isModularUnit() || !workspaceReady || !modularWorkspace.openTabs.length)");
    expect(routeSource).not.toContain("for (const moduleId of modularWorkspace.openTabs)");
  });
});
