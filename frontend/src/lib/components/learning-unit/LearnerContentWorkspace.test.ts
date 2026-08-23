import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";

import LearnerContentWorkspace from "./LearnerContentWorkspace.svelte";
import type { ContentGroup } from "$lib/learning-unit/workspace";

const groups: ContentGroup[] = [
  {
    id: "module-1",
    title: "Grundlagen",
    items: [
      {
        key: "material:material-1",
        kind: "material",
        title: "Grundrechte und Privatsphäre",
        position: 1,
        contextLabel: "Grundlagen",
        moduleId: "module-1",
        material: {
          id: "material-1",
          title: "Grundrechte und Privatsphäre",
          kind: "markdown",
          body_md: "Ein längerer Materialtext."
        }
      },
      {
        key: "material:material-2",
        kind: "material",
        title: "Grenzen digitaler Überwachung",
        position: 2,
        contextLabel: "Grundlagen",
        moduleId: "module-1",
        material: {
          id: "material-2",
          title: "Grenzen digitaler Überwachung",
          kind: "markdown",
          body_md: "Ein zweiter vollständiger Materialtext."
        }
      },
      {
        key: "task:task-1",
        kind: "task",
        title: "Aufgabe 1",
        position: 3,
        contextLabel: "Grundlagen",
        moduleId: "module-1",
        task: {
          id: "task-1",
          instruction_md: "Begründe deine Position zur Chatkontrolle.",
          criteria: [],
          kind: "native"
        }
      }
    ]
  },
  {
    id: "module-2",
    title: "Argumente",
    items: []
  }
];

const dialogGroups: ContentGroup[] = [
  {
    id: "module-dialog",
    title: "Quellenanalyse",
    items: [
      {
        key: "task:task-dialog",
        kind: "task",
        title: "Aufgabe 1",
        position: 1,
        contextLabel: "Quellenanalyse",
        moduleId: "module-dialog",
        task: {
          id: "task-dialog",
          instruction_md: "Untersuche die Quelle im Gespräch.",
          criteria: [],
          kind: "dialog",
          dialog: {
            partner_name: "Archivarin Ada",
            partner_description_md: "Eine sachkundige Gesprächspartnerin.",
            opening_message_md: "Welche Beobachtung möchtest du zuerst untersuchen?",
            response_mode: "free_text",
            max_rounds: 2,
            closing_prompt_md: null
          }
        }
      }
    ]
  }
];

function baseProps() {
  return {
    learnerSub: "student-1",
    courseId: "course-1",
    unitTitle: "Chatkontrolle in Europa",
    unitType: "modular" as const,
    contentGroups: groups,
    mode: "orienting" as const,
    activeTaskKey: null,
    activeEditorMode: null,
    compactSurface: "task" as const,
    navigationVisible: true,
    collapsedItemKeys: [],
    contextModules: [
      {
        id: "module-1",
        title: "Grundlagen",
        current: true,
        closable: false,
        loaded: true,
        loading: false,
        error: null,
        items: groups[0].items
      },
      {
        id: "module-2",
        title: "Argumente",
        current: false,
        closable: true,
        loaded: true,
        loading: false,
        error: null,
        items: groups[1].items
      }
    ],
    expandedContextModuleIds: [],
    expandedModuleMaterialKeys: {},
    expandedSubmissionModuleIds: [],
    expandedSubmissionKeys: [],
    historyByTask: {},
    historyStateByTask: {},
    onBeginTask: vi.fn(),
    onPauseTask: vi.fn(),
    onCloseModule: vi.fn(),
    onSetCompactSurface: vi.fn(),
    onToggleMaterial: vi.fn(),
    onToggleContextModuleMaterial: vi.fn(),
    onOpenContextReference: vi.fn(),
    onProgressPersisted: vi.fn()
  };
}

describe("LearnerContentWorkspace", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders stacked modules and a compact task row in orientation mode", async () => {
    const props = baseProps();
    const { container } = render(LearnerContentWorkspace, { props });

    expect(screen.getByRole("region", { name: "Orientieren" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Chatkontrolle in Europa", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Grundlagen" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Argumente" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Modul schließen" })).toHaveLength(2);
    expect(container.querySelectorAll(".learner-orientation__module")).toHaveLength(2);
    expect(container.querySelector(".learner-task-workbench")).toBeNull();
    expect(screen.getByText("Ein längerer Materialtext.")).toBeInTheDocument();

    await fireEvent.click(screen.getByRole("button", { name: "Aufgabe 1 beginnen" }));
    expect(props.onBeginTask).toHaveBeenCalledWith("task:task-1", "text");
  });

  it("renders only the active task outside the module list in work mode", async () => {
    const props = {
      ...baseProps(),
      mode: "working" as const,
      activeTaskKey: "task:task-1",
      activeEditorMode: "text" as const
    };
    props.contextModules[1].items = [
      {
        key: "material:material-3",
        kind: "material",
        title: "Perspektiven aus Argumente",
        position: 1,
        contextLabel: "Argumente",
        moduleId: "module-2",
        material: {
          id: "material-3",
          title: "Perspektiven aus Argumente",
          kind: "markdown",
          body_md: "Ein ergänzender Materialtext."
        }
      }
    ];
    const { container } = render(LearnerContentWorkspace, { props });

    expect(screen.queryByRole("region", { name: "Orientieren" })).not.toBeInTheDocument();
    expect(container.querySelectorAll(".learner-task-workbench")).toHaveLength(1);
    expect(container.querySelector(".learner-orientation__module")?.closest(".learner-surface--inactive")).not.toBeNull();
    expect(screen.queryByRole("button", { name: "Aufgabe 1 beginnen" })).not.toBeInTheDocument();

    const context = screen.getByRole("complementary", { name: "Aufgabe und Kontext" });
    const work = screen.getByRole("main", { name: "Bearbeitung" });
    expect(within(context).getByText("Begründe deine Position zur Chatkontrolle.")).toBeInTheDocument();
    const compactStatement = within(work).getByRole("region", { name: "Vollständige Aufgabenstellung" });
    expect(within(compactStatement).getByText("Begründe deine Position zur Chatkontrolle.")).toBeInTheDocument();
    const focusedMaterials = within(context).getByRole("region", { name: "Materialien zur Aufgabe" });
    expect(within(focusedMaterials).getByText("Grundrechte und Privatsphäre")).toBeInTheDocument();
    expect(within(focusedMaterials).getByText("Ein längerer Materialtext.")).toBeInTheDocument();
    expect(within(focusedMaterials).getByText("Ein zweiter vollständiger Materialtext.")).toBeInTheDocument();
    expect(container.querySelector(".learner-focused-material-card__visual")).toBeNull();
    const firstMaterialToggle = within(focusedMaterials).getByRole("button", {
      name: "Grundrechte und Privatsphäre ein- oder ausklappen"
    });
    expect(firstMaterialToggle).toHaveAttribute("aria-expanded", "true");
    expect(within(focusedMaterials).getByRole("button", {
      name: "Grenzen digitaler Überwachung ein- oder ausklappen"
    })).toHaveAttribute("aria-expanded", "false");
    expect(within(focusedMaterials).getByRole("button", {
      name: "Grundrechte und Privatsphäre groß lesen"
    })).toBeInTheDocument();
    await fireEvent.click(firstMaterialToggle);
    expect(props.onToggleContextModuleMaterial).toHaveBeenCalledWith("module-1", "material:material-1");
    await fireEvent.click(within(focusedMaterials).getByRole("button", {
      name: "Grundrechte und Privatsphäre groß lesen"
    }));
    expect(props.onOpenContextReference).toHaveBeenCalledWith("material:material-1");
    expect(within(context).queryByText("Material · Aktuelles Modul")).not.toBeInTheDocument();
    expect(within(context).queryByRole("button", { name: /anheften|lösen/i })).not.toBeInTheDocument();
    expect(within(context).queryByText("Material suchen")).not.toBeInTheDocument();
    await fireEvent.click(within(context).getByText("Weitere Materialien und eigene Abgaben"));
    expect(within(context).getByRole("button", {
      name: "Perspektiven aus Argumente ein- oder ausklappen"
    })).toHaveAttribute("aria-expanded", "true");
    expect(within(context).getByRole("button", { name: "Perspektiven aus Argumente groß lesen" })).toBeInTheDocument();
    expect(within(context).getAllByText("Grundrechte und Privatsphäre")).toHaveLength(1);
    expect(within(context).getByRole("heading", { name: "Argumente", level: 4 })).toBeInTheDocument();
    expect(within(context).queryByText("Aktuell")).toBeNull();
    expect(within(context).getByRole("button", { name: "Modul Argumente schließen" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Zurück zu Modul Grundlagen/ })).toBeInTheDocument();
    expect(within(context).queryByRole("button", { name: "Pausieren" })).not.toBeInTheDocument();
  });

  it("continues with the next non-final task in the same module", async () => {
    const onBeginTask = vi.fn();
    const taskTwo = {
      key: "task:task-2",
      kind: "task" as const,
      title: "Aufgabe 2",
      position: 4,
      contextLabel: "Grundlagen",
      moduleId: "module-1",
      task: {
        id: "task-2",
        instruction_md: "Diese Aufgabe ist bereits abgeschlossen.",
        criteria: [],
        kind: "native" as const,
        latest_final_submission_at: "2026-08-22T10:00:00Z"
      }
    };
    const taskThree = {
      key: "task:task-3",
      kind: "task" as const,
      title: "Aufgabe 3",
      position: 5,
      contextLabel: "Grundlagen",
      moduleId: "module-1",
      task: {
        id: "task-3",
        instruction_md: "Diese Aufgabe ist noch offen.",
        criteria: [],
        kind: "native" as const
      }
    };
    const contentGroups: ContentGroup[] = [
      {
        ...groups[0],
        items: [...groups[0].items, taskTwo, taskThree]
      },
      groups[1]
    ];
    const props = {
      ...baseProps(),
      contentGroups,
      contextModules: [
        {
          ...baseProps().contextModules[0],
          items: contentGroups[0].items
        }
      ],
      mode: "working" as const,
      workStatus: "result" as const,
      activeTaskKey: "task:task-1",
      activeEditorMode: "text" as const,
      onBeginTask,
      historyByTask: {
        "task-1": [
          {
            id: "33333333-3333-4333-8333-333333333333",
            attempt_nr: 2,
            kind: "text" as const,
            intent: "submit" as const,
            created_at: "2026-08-23T10:00:00Z",
            analysis_status: "completed" as const,
            text_body: "Meine endgültige Fassung",
            feedback_md: "Gut abgeschlossen."
          }
        ]
      }
    };

    render(LearnerContentWorkspace, { props });
    await fireEvent.click(screen.getByRole("button", { name: "Weiter zu Aufgabe 3" }));

    expect(onBeginTask).toHaveBeenCalledWith("task:task-3", "text");
  });

  it("connects the adjustable column separator to normal task layout state", async () => {
    const onPreviewTaskColumnRatio = vi.fn();
    const onCommitTaskColumnRatio = vi.fn();
    const props = {
      ...baseProps(),
      mode: "working" as const,
      activeTaskKey: "task:task-1",
      activeEditorMode: "text" as const,
      taskColumnRatio: 52,
      onPreviewTaskColumnRatio,
      onCommitTaskColumnRatio
    };
    const { container } = render(LearnerContentWorkspace, { props });

    const separator = screen.getByRole("separator", { name: "Spaltenbreite anpassen" });
    expect(separator).toHaveAttribute("aria-valuenow", "52");
    expect(container.querySelector(".learner-task-workbench__desk")).toHaveStyle(
      "--learner-task-column-ratio: 52%"
    );

    await fireEvent.keyDown(separator, { key: "ArrowRight" });
    expect(onPreviewTaskColumnRatio).toHaveBeenLastCalledWith(53);
    expect(onCommitTaskColumnRatio).toHaveBeenLastCalledWith(53);
  });

  it("renders the shared task context exactly once for dialogs", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            session: {
              id: "session-dialog",
              status: "active",
              round_count: 0,
              dialog: dialogGroups[0].items[0].task?.dialog,
              closing_answer_md: null,
              initial_sentence_starters: [],
              initial_starters_status: "not_required",
              initial_generation_attempts: 0,
              turns: []
            }
          }),
          { status: 200, headers: { "content-type": "application/json" } }
        )
      )
    );
    const props = {
      ...baseProps(),
      contentGroups: dialogGroups,
      mode: "working" as const,
      activeTaskKey: "task:task-dialog",
      activeEditorMode: "text" as const
    };
    const { container } = render(LearnerContentWorkspace, { props });

    expect(await screen.findByRole("complementary", { name: "Aufgabe und Kontext" })).toBeInTheDocument();
    expect(container.querySelectorAll(".learner-task-context")).toHaveLength(1);
    expect(container.querySelectorAll(".dialog-sidebar")).toHaveLength(1);
    expect(screen.getAllByRole("navigation", { name: "Arbeitsbereich wählen" })).toHaveLength(1);
    const statement = screen.getByRole("region", { name: "Vollständige Aufgabenstellung" });
    expect(within(statement).getByText("Untersuche die Quelle im Gespräch.")).toBeInTheDocument();
  });

  it("binds persisted progress to the task that created the async callback", () => {
    const source = readFileSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)), "LearnerContentWorkspace.svelte"), "utf8");

    expect(source).toContain("onProgressPersisted?.(task.id, submission)");
  });

  it("keeps task and material surfaces mounted while changing the compact view", async () => {
    const props = {
      ...baseProps(),
      mode: "working" as const,
      activeTaskKey: "task:task-1",
      activeEditorMode: "text" as const,
      compactSurface: "materials" as const
    };
    const { container } = render(LearnerContentWorkspace, { props });

    expect(container.querySelector('[data-work-surface="task"]')).not.toBeNull();
    expect(container.querySelector('[data-work-surface="materials"]')).not.toBeNull();
    expect(container.querySelector(".learner-task-workbench")).toHaveAttribute(
      "data-compact-surface",
      "materials"
    );

    await fireEvent.click(screen.getByRole("button", { name: "Aufgabe" }));
    expect(props.onSetCompactSurface).toHaveBeenCalledWith("task");
  });

  it("renders opened modules without a second source-management workflow", async () => {
    const onContextScroll = vi.fn();
    const onWorkScroll = vi.fn();
    const onCloseModule = vi.fn();
    const onUndoCloseModule = vi.fn();
    const props = {
      ...baseProps(),
      mode: "working" as const,
      activeTaskKey: "task:task-1",
      activeEditorMode: "text" as const,
      compactSurface: "materials" as const,
      expandedContextModuleIds: ["module-2"],
      contextScrollTop: 240,
      workScrollTop: 80,
      closedContextModuleTitle: "Vertiefung",
      onContextScroll,
      onWorkScroll,
      onCloseModule,
      onUndoCloseModule,
      contextModules: [
        {
          id: "module-1",
          title: "Grundlagen",
          current: true,
          closable: false,
          loaded: true,
          loading: false,
          error: null,
          items: groups[0].items
        },
        {
          id: "module-2",
          title: "Vertiefung",
          current: false,
          closable: true,
          loaded: true,
          loading: false,
          error: null,
          items: [{
            key: "material:material-3",
            kind: "material" as const,
            title: "Positionen im Parlament",
            position: 1,
            contextLabel: "Vertiefung",
            moduleId: "module-2",
            material: { id: "material-3", title: "Positionen im Parlament", kind: "markdown" as const, body_md: "Text aus dem geöffneten Modul." }
          }]
        }
      ]
    };
    const { container, rerender } = render(LearnerContentWorkspace, { props });

    await fireEvent.click(screen.getByText("Weitere Materialien und eigene Abgaben"));
    expect(screen.getByText("Text aus dem geöffneten Modul.")).toBeInTheDocument();
    expect(screen.queryByText("Angeheftet")).not.toBeInTheDocument();
    expect(screen.queryByText("Material suchen")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /anheften|lösen/i })).not.toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Modul Vertiefung schließen" }));
    expect(onCloseModule).toHaveBeenCalledWith("module-2");
    await fireEvent.click(screen.getByRole("button", { name: "Rückgängig" }));
    expect(onUndoCloseModule).toHaveBeenCalledOnce();

    const scrollSurface = container.querySelector<HTMLElement>(".learner-task-context__scroll");
    expect(scrollSurface?.scrollTop).toBe(240);
    if (scrollSurface) {
      scrollSurface.scrollTop = 410;
      fireEvent.scroll(scrollSurface);
    }
    expect(onContextScroll).toHaveBeenCalledWith(410);

    await rerender({ ...props, contextScrollTop: 120 });
    expect(scrollSurface?.scrollTop).toBe(410);

    const workSurface = container.querySelector<HTMLElement>(".learner-task-workbench__main");
    expect(workSurface?.scrollTop).toBe(80);
    if (workSurface) {
      workSurface.scrollTop = 290;
      await fireEvent.scroll(workSurface);
    }
    expect(onWorkScroll).toHaveBeenCalledWith(290);
    await rerender({ ...props, contextScrollTop: 120, workScrollTop: 20 });
    expect(workSurface?.scrollTop).toBe(290);
  });

  it("opens a deliberately selected document across the workbench while keeping the desk mounted", async () => {
    const onCloseContextReader = vi.fn();
    const onReaderScroll = vi.fn();
    const focusSpy = vi.spyOn(HTMLElement.prototype, "focus");
    const props = {
      ...baseProps(),
      mode: "working" as const,
      activeTaskKey: "task:task-1",
      activeEditorMode: "text" as const,
      readingReferenceKey: "material:material-1",
      readerScrollTop: 120,
      onCloseContextReader,
      onReaderScroll,
      contextModules: [
        {
          id: "module-1",
          title: "Grundlagen",
          current: true,
          closable: false,
          loaded: true,
          loading: false,
          error: null,
          items: groups[0].items
        }
      ]
    };
    const { container, rerender } = render(LearnerContentWorkspace, { props });

    const reader = screen.getByRole("region", { name: "Dokument groß lesen" });
    await vi.waitFor(() => expect(focusSpy).toHaveBeenCalledWith({ preventScroll: true }));
    expect(within(reader).getByRole("article", { name: "Grundrechte und Privatsphäre" })).toBeInTheDocument();
    expect(within(reader).getByText("Ein längerer Materialtext.")).toBeInTheDocument();
    expect(container.querySelector(".learner-task-workbench__desk")).toHaveAttribute("inert");
    expect(container.querySelector(".learner-task-workbench__desk")).toHaveAttribute("aria-hidden", "true");
    expect(container.querySelector('[data-work-surface="task"]')).not.toBeNull();

    const readerScroll = container.querySelector<HTMLElement>(".learner-context-reader__scroll");
    expect(readerScroll?.scrollTop).toBe(120);
    if (readerScroll) {
      readerScroll.scrollTop = 260;
      await fireEvent.scroll(readerScroll);
    }
    expect(onReaderScroll).toHaveBeenCalledWith(260);
    await rerender({ ...props, readerScrollTop: 40 });
    expect(readerScroll?.scrollTop).toBe(260);
    await fireEvent.click(within(reader).getByRole("button", { name: "Zurück zur Aufgabe" }));
    expect(onCloseContextReader).toHaveBeenCalledOnce();
  });

  it("keeps the workbench flat and switches layout from its own available width", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const css = readFileSync(path.resolve(currentDir, "../../styles/learning-unit.css"), "utf8");

    expect(css).toMatch(/\.learning-unit-stage--content\s*\{[^}]*container-type:\s*inline-size;/s);
    expect(css).toMatch(/\.learner-task-workbench-container\s*\{[^}]*grid-template-rows:\s*minmax\(3\.25rem,\s*auto\) auto;/s);
    expect(css).toMatch(/\.learner-task-workbench\s*\{[^}]*border:\s*0;[^}]*background:\s*transparent;[^}]*box-shadow:\s*none;/s);
    expect(css).toContain("@container (min-width: 60rem)");
    expect(css).toMatch(/grid-template-columns:\s*var\(--learner-task-column-ratio,\s*clamp\(32rem,\s*44cqw,\s*38rem\)\) 1px minmax\(0,\s*1fr\)/);
    expect(css).not.toContain("@container learning-dialog (min-width: 64rem)");
    expect(css).toMatch(/\.learner-task-context__scroll\s*\{[^}]*overflow-y:\s*auto;/s);
    expect(css).toMatch(/\.learner-reference-document__prose\s*\{[^}]*max-width:\s*68ch;/s);
  });

  it("keeps opened-module context styles local, responsive and free of pinning controls", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const css = readFileSync(path.resolve(currentDir, "../../styles/learning-unit.css"), "utf8");
    const component = readFileSync(path.resolve(currentDir, "LearnerContentWorkspace.svelte"), "utf8");
    const materialContext = readFileSync(path.resolve(currentDir, "LearnerMaterialContext.svelte"), "utf8");
    const taskContext = readFileSync(path.resolve(currentDir, "LearnerTaskContext.svelte"), "utf8");

    expect(component).toContain("<LearnerTaskContext");
    expect(taskContext).toContain("<LearnerFocusedMaterialContext");
    expect(taskContext).toContain('class="learner-task-context__all-materials"');
    expect(taskContext).toContain("Weitere Materialien und eigene Abgaben");
    expect(materialContext).not.toContain("Angeheftet");
    expect(materialContext).not.toContain("Material suchen");
    expect(materialContext).not.toContain("aria-pressed");
    expect(css).not.toContain(".learner-context-picker");
    expect(css).not.toContain(".learner-task-context__pinned");
    expect(css).toContain(".learner-material-context__module");
    expect(css).toMatch(/\.learner-material-context__tree-children\s*\{[^}]*border-inline-start:/s);
    expect(css).toMatch(/\.learner-material-context__tree-item::before\s*\{[^}]*border-block-start:/s);
    expect(css).toMatch(/\.learner-material-context__tree-item--submission\s*\{[^}]*margin-inline-start:/s);
    expect(css).toMatch(/\.learner-tree-chevron--expanded\s*\{[^}]*transform:\s*rotate\(90deg\)/s);
    expect(css).toMatch(/@container\s*\(max-width:\s*32rem\)[\s\S]*\.learner-material-context__tree-children\s*\{[^}]*padding-inline-start:/s);
    expect(css).toMatch(/\.learner-material-context__module-toggle\s*\{[^}]*min-height:\s*2\.75rem;/s);
  });
});
