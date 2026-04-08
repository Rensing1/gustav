import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("learning unit route contract", () => {
  it("uses the shared workspace settings menu instead of the local legacy layout menu", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const appCss = readFileSync(path.resolve(currentDir, "../../../../../../lib/styles/app.css"), "utf8");
    const designSystemCss = readFileSync(path.resolve(currentDir, "../../../../../../lib/styles/design-system.css"), "utf8");
    const designDoc = readFileSync(path.resolve(currentDir, "../../../../../../../../docs/DESIGN.md"), "utf8");

    expect(routeSource).toContain('import WorkspaceSettingsMenu from "$lib/components/ui/WorkspaceSettingsMenu.svelte";');
    expect(routeSource).toContain("<WorkspaceSettingsMenu");
    expect(routeSource).toContain('class="learning-unit-toolbar__utility"');
    expect(routeSource).toContain('class="learning-unit-layout-frame learning-unit-layout-frame--toolbar"');
    expect(routeSource).toContain("layoutMenuEnabled={false}");
    expect(routeSource).toContain("modularSettingsMenuOpen = !modularSettingsMenuOpen");
    expect(routeSource).toContain('!target.closest("[data-layout-menu-root]")');
    expect(routeSource).toContain('if (event.key === "Escape")');
    expect(routeSource).not.toContain('<div class="learning-unit-layout-rail">\n        <div class="learning-unit-layout-frame learning-unit-layout-frame--toolbar">');
    expect(routeSource).not.toContain("learning-unit-layout-menu");
    expect(appCss).not.toContain(".learning-unit-layout-menu");
    expect(designDoc).toContain("## 7. Form, Raum und Bewegung");
    expect(designDoc).toContain("### 7.1 Spacing");
    expect(designDoc).toContain("### 7.3 Flächen");
    expect(designDoc).toContain("### 11.3 Inhalte");
    expect(designDoc).toContain("Lernraum-spezifische Overrides unter `.learning-unit-content-shell` gehören in");
    expect(designDoc).toContain("den finalen Designsystem-Layer in `frontend/src/lib/styles/design-system.css`");
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

  it("keeps pane item lists intact while tracking a single inline submission focus", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    expect(routeSource).toContain("function setSubmissionWorkspace");
    expect(routeSource).toContain("let reviewFocusByPane = $state<ReviewFocusByPane>(emptyReviewFocus())");
    expect(routeSource).toContain("togglePaneSubmissionFocus");
    expect(routeSource).toContain("togglePaneReviewFocus");
    expect(routeSource).toContain("setPaneReviewFocus");
    expect(routeSource).toContain("function toggleReviewPanel(paneId: PaneId, taskId: string)");
    expect(routeSource).not.toContain("reviewPanelOpenByTask");
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
    const taskCardSource = readFileSync(
      path.resolve(currentDir, "../../../../../../lib/components/learning-unit/LearningTaskCard.svelte"),
      "utf8"
    );

    expect(routeSource).toContain("let submissionHistoryByTask = $state.raw<Record<string, LearningSubmission[]>>({})");
    expect(routeSource).toContain("function historyForTask(taskId: string): LearningSubmission[]");
    expect(routeSource).not.toContain("let historyState = $state<LearningSubmission[]>(data.history)");
    expect(workspaceSource).toContain("historyByTask");
    expect(workspaceSource).toContain("history={historyByTask[task.id] ?? []}");
    expect(workspaceSource).toContain("compactLayout={true}");
    expect(workspaceSource).toContain('class="learning-unit-module"');
    expect(workspaceSource).toContain('class="learning-unit-module__index"');
    expect(workspaceSource).toContain('class="learning-unit-module__meta"');
    expect(workspaceSource).toContain('class="learning-unit-module__materials"');
    expect(workspaceSource).toContain('class="learning-unit-module__tasks"');
    expect(workspaceSource).toContain("moduleDisplayIndex(groupIndex)");
    expect(workspaceSource).toContain("moduleMetaText(group)");
    expect(workspaceSource).not.toContain('<p class="workspace-label">Modul</p>');
    expect(workspaceSource).toContain("{#if group.materials.length}");
    expect(workspaceSource).toContain('class="learning-unit-workspace-surface"');
    expect(taskCardSource).toContain("learning-task-row__preview");
    expect(taskCardSource).toContain("taskPreviewLine()");
    expect(taskCardSource).toContain("return `${taskTitle} beginnen`;");
    expect(taskCardSource).not.toContain("compactStatusLabel()");
    expect(workspaceSource).not.toContain("{history}");
  });

  it("reopens modular materials on restore and module reopen instead of persisting them closed", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    expect(routeSource).toContain("reopenMaterialEntries");
    expect(routeSource).toContain("function reopenModularMaterials");
    expect(routeSource).toContain("reopenModularMaterials(moduleIds)");
    expect(routeSource).toContain("reopenModularMaterials([moduleId])");
  });

  it("derives modular spacing from DESIGN.md instead of flattening modules into one continuous list", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const appCss = readFileSync(path.resolve(currentDir, "../../../../../../lib/styles/app.css"), "utf8");
    const designSystemCss = readFileSync(path.resolve(currentDir, "../../../../../../lib/styles/design-system.css"), "utf8");
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
    expect(appCss).toMatch(
      /\.learning-unit-module__meta\s*\{[^}]*font-family:\s*var\(--font-technical\);[^}]*font-size:\s*calc\(0\.82rem \* var\(--learning-unit-label-scale\)\);/s
    );
    expect(appCss).toMatch(
      /\.learning-unit-module__section-head h5\s*\{[^}]*font-size:\s*calc\(1\.02rem \* var\(--learning-unit-label-scale\)\);[^}]*font-weight:\s*800;/s
    );
    expect(appCss).toMatch(
      /\.learning-task-row\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+auto;/s
    );
    expect(appCss).toMatch(/\.learning-task-row__preview\s*\{[^}]*white-space:\s*nowrap;[^}]*text-overflow:\s*ellipsis;/s);
    expect(designDoc).toContain("kompakte Task-Zeilen im modularen Lernraum nutzen eine Vorschauzeile");
    expect(designDoc).toContain("Status wird primär über Balken und Tönung getragen");
    expect(designDoc).toContain("Die vollständige Aufgabenstellung erscheint in der aktiven Detailansicht inline");
    expect(designDoc).toContain("`Meine Abgabe` und Bearbeitung sind pro Pane exklusiv und erneut klickbar");
  });

  it("uses one subtle card per module while keeping the pane surface itself cardless", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const appCss = readFileSync(path.resolve(currentDir, "../../../../../../lib/styles/app.css"), "utf8");
    const designSystemCss = readFileSync(path.resolve(currentDir, "../../../../../../lib/styles/design-system.css"), "utf8");
    const designDoc = readFileSync(path.resolve(currentDir, "../../../../../../../../docs/DESIGN.md"), "utf8");

    expect(designDoc).toContain("### 7.3 Flächen");
    expect(designDoc).toContain("### 11.3 Inhalte");
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

  it("lets the learner workspace use the viewport width instead of capping the content area in the center", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const workspaceSource = readFileSync(
      path.resolve(currentDir, "../../../../../../lib/components/learning-unit/LearningUnitContentWorkspace.svelte"),
      "utf8"
    );
    const appCss = readFileSync(path.resolve(currentDir, "../../../../../../lib/styles/app.css"), "utf8");
    const designDoc = readFileSync(path.resolve(currentDir, "../../../../../../../../docs/DESIGN.md"), "utf8");

    expect(designDoc).toContain("### 7.1 Spacing");
    expect(designDoc).toContain("### 11.3 Inhalte");
    expect(appCss).not.toMatch(/\.learning-unit-pane-grid--single\s*\{[^}]*48rem/s);
    expect(appCss).toMatch(
      /\.learning-unit-space\.workspace-page--learner-unit-content\s*\{[^}]*width:\s*100vw;[^}]*margin-left:\s*calc\(50%\s*-\s*50vw\);/s
    );
    expect(appCss).toMatch(/\.learning-unit-layout-frame\s*\{[^}]*width:\s*min\(100%,\s*var\(--learning-unit-workspace-width\)\);/s);
    expect(routeSource).toContain('class="learning-unit-layout-rail"');
    expect(routeSource).toContain('class="learning-unit-layout-frame"');
    expect(workspaceSource).not.toContain('class="learning-unit-layout-rail"');
    expect(workspaceSource).not.toContain('class="learning-unit-layout-frame"');
  });

  it("removes horizontal page separators while keeping task rows as the primary objects", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const appCss = readFileSync(path.resolve(currentDir, "../../../../../../lib/styles/app.css"), "utf8");
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
    expect(routeSource).toContain("view: \"overview\"");
    expect(routeSource).not.toContain("if (!isModularUnit() || !workspaceReady || !modularWorkspace.openTabs.length)");
    expect(routeSource).not.toContain("for (const moduleId of modularWorkspace.openTabs)");
  });
});
