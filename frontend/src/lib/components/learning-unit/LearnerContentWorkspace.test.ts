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
    expandedSubmissionModuleIds: [],
    expandedSubmissionKeys: [],
    historyByTask: {},
    historyStateByTask: {},
    onBeginTask: vi.fn(),
    onPauseTask: vi.fn(),
    onCloseModule: vi.fn(),
    onSetCompactSurface: vi.fn(),
    onToggleMaterial: vi.fn(),
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

  it("renders only the active task outside the module list in work mode", () => {
    const props = {
      ...baseProps(),
      mode: "working" as const,
      activeTaskKey: "task:task-1",
      activeEditorMode: "text" as const
    };
    const { container } = render(LearnerContentWorkspace, { props });

    expect(screen.queryByRole("region", { name: "Orientieren" })).not.toBeInTheDocument();
    expect(container.querySelectorAll(".learner-task-workbench")).toHaveLength(1);
    expect(container.querySelector(".learner-orientation__module")?.closest(".learner-surface--inactive")).not.toBeNull();
    expect(screen.queryByRole("button", { name: "Aufgabe 1 beginnen" })).not.toBeInTheDocument();

    const context = screen.getByRole("complementary", { name: "Aufgabe und Kontext" });
    const work = screen.getByRole("main", { name: "Bearbeitung" });
    expect(within(context).getByText("Begründe deine Position zur Chatkontrolle.")).toBeInTheDocument();
    expect(within(work).queryByText("Begründe deine Position zur Chatkontrolle.")).not.toBeInTheDocument();
    expect(within(context).getByRole("heading", { name: /Grundlagen/, level: 4 })).toBeInTheDocument();
    expect(within(context).getByText("Aktuell")).toBeInTheDocument();
    expect(within(context).getByText("Grundrechte und Privatsphäre")).toBeInTheDocument();
    expect(within(context).getByText("Ein längerer Materialtext.")).toBeInTheDocument();
    expect(within(context).queryByText("Ein zweiter vollständiger Materialtext.")).not.toBeInTheDocument();
    expect(within(context).queryByText("Material · Aktuelles Modul")).not.toBeInTheDocument();
    expect(within(context).queryByRole("button", { name: /anheften|lösen/i })).not.toBeInTheDocument();
    expect(within(context).queryByText("Material suchen")).not.toBeInTheDocument();
    expect(within(context).getByRole("button", { name: "Modul Argumente schließen" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Zurück zu Modul Grundlagen/ })).toBeInTheDocument();
    expect(within(context).queryByRole("button", { name: "Pausieren" })).not.toBeInTheDocument();
  });

  it("renders dialog context once instead of nesting the generic task context", async () => {
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

    expect(await screen.findByRole("complementary", { name: "Dialogpartner und Sitzungsaktionen" })).toBeInTheDocument();
    expect(container.querySelector(".learner-task-context")).toBeNull();
    expect(container.querySelectorAll(".dialog-sidebar")).toHaveLength(1);
    expect(screen.getAllByRole("navigation", { name: "Arbeitsbereich wählen" })).toHaveLength(1);
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
      closedContextModuleTitle: "Vertiefung",
      onContextScroll,
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
    const { container } = render(LearnerContentWorkspace, { props });

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
    const { container } = render(LearnerContentWorkspace, { props });

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
    await fireEvent.click(within(reader).getByRole("button", { name: "Zurück zur Aufgabe" }));
    expect(onCloseContextReader).toHaveBeenCalledOnce();
  });

  it("keeps the workbench flat and switches layout from its own available width", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const css = readFileSync(path.resolve(currentDir, "../../styles/learning-unit.css"), "utf8");

    expect(css).toMatch(/\.learning-unit-stage--content\s*\{[^}]*container-type:\s*inline-size;/s);
    expect(css).toMatch(/\.learner-task-workbench-container\s*\{[^}]*grid-template-rows:\s*minmax\(3\.25rem,\s*auto\) auto;/s);
    expect(css).toMatch(/\.learner-task-workbench\s*\{[^}]*border:\s*0;[^}]*background:\s*transparent;[^}]*box-shadow:\s*none;/s);
    expect(css).toContain("@container (min-width: 72rem)");
    expect(css).toMatch(/grid-template-columns:\s*clamp\(32rem,\s*44cqw,\s*38rem\) minmax\(0,\s*1fr\)/);
    expect(css).not.toContain("@container learning-dialog (min-width: 64rem)");
    expect(css).toMatch(/\.learner-task-context__scroll\s*\{[^}]*overflow-y:\s*auto;/s);
    expect(css).toMatch(/\.learner-reference-document__prose\s*\{[^}]*max-width:\s*68ch;/s);
  });

  it("keeps opened-module context styles local, responsive and free of pinning controls", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const css = readFileSync(path.resolve(currentDir, "../../styles/learning-unit.css"), "utf8");
    const component = readFileSync(path.resolve(currentDir, "LearnerContentWorkspace.svelte"), "utf8");
    const materialContext = readFileSync(path.resolve(currentDir, "LearnerMaterialContext.svelte"), "utf8");

    expect(component).toContain("<LearnerMaterialContext");
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
