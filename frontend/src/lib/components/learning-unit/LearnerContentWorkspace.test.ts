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
        key: "task:task-1",
        kind: "task",
        title: "Aufgabe 1",
        position: 2,
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
    expect(within(context).getByText("Grundrechte und Privatsphäre")).toBeInTheDocument();
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

  it("renders current and pinned references as one deduplicated document stack", async () => {
    const onContextScroll = vi.fn();
    const onToggleContextReference = vi.fn();
    const previousAnswer = "Meine ausführliche frühere Begründung mit mehreren Argumenten und Belegen.";
    const props = {
      ...baseProps(),
      mode: "working" as const,
      activeTaskKey: "task:task-1",
      activeEditorMode: "text" as const,
      compactSurface: "materials" as const,
      expandedReferenceKeys: ["submission:task-2"],
      manualContextReferences: [
        {
          key: "material:material-1",
          kind: "material" as const,
          id: "material-1",
          moduleId: "module-1",
          taskId: null
        },
        {
          key: "submission:task-2",
          kind: "submission" as const,
          id: "task-2",
          moduleId: "module-2",
          taskId: "task-2"
        }
      ],
      contextScrollTop: 240,
      onContextScroll,
      onToggleContextReference,
      contextModules: [
        {
          id: "module-1",
          title: "Grundlagen",
          current: true,
          loaded: true,
          loading: false,
          error: null,
          items: groups[0].items
        },
        {
          id: "module-2",
          title: "Argumente",
          current: false,
          loaded: true,
          loading: false,
          error: null,
          items: [
            {
              key: "task:task-2",
              kind: "task" as const,
              title: "Frühere Analyse",
              position: 1,
              contextLabel: "Argumente",
              moduleId: "module-2",
              task: { id: "task-2", instruction_md: "Analysiere.", criteria: [], kind: "native" as const }
            }
          ]
        }
      ],
      historyByTask: {
        "task-2": [
          {
            id: "submission-1",
            intent: "submit" as const,
            attempt_nr: 1,
            kind: "text" as const,
            created_at: "2026-08-03T10:00:00+00:00",
            analysis_status: "completed" as const,
            text_body: previousAnswer
          }
        ]
      }
    };
    const { container } = render(LearnerContentWorkspace, { props });

    expect(screen.queryByRole("article", { name: "Kontext lesen" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("article", { name: "Grundrechte und Privatsphäre" })).toHaveLength(1);
    expect(screen.getByRole("article", { name: "Frühere Analyse" })).toBeInTheDocument();
    expect(screen.getByText(previousAnswer)).toBeInTheDocument();
    expect(container.querySelector('[data-work-surface="task"]')).not.toBeNull();
    const scrollSurface = container.querySelector<HTMLElement>(".learner-task-context__scroll");
    expect(scrollSurface).not.toBeNull();
    expect(scrollSurface?.scrollTop).toBe(240);

    if (scrollSurface) {
      scrollSurface.scrollTop = 410;
      fireEvent.scroll(scrollSurface);
    }
    expect(onContextScroll).toHaveBeenCalledWith(410);

    await fireEvent.click(screen.getByRole("button", { name: "Frühere Analyse ein- oder ausklappen" }));
    expect(onToggleContextReference).toHaveBeenCalledWith("submission:task-2");
  });

  it("loads module groups lazily and offers materials and own submissions individually", async () => {
    const onToggleContextModule = vi.fn();
    const onAddContextReference = vi.fn();
    const props = {
      ...baseProps(),
      mode: "working" as const,
      activeTaskKey: "task:task-1",
      activeEditorMode: "text" as const,
      compactSurface: "materials" as const,
      contextPickerOpen: true,
      expandedContextModuleIds: ["module-2"],
      onToggleContextModule,
      onAddContextReference,
      contextModules: [
        {
          id: "module-2",
          title: "Argumente",
          current: false,
          loaded: true,
          loading: false,
          error: null,
          items: [
            {
              key: "material:material-2",
              kind: "material" as const,
              title: "Positionen im Parlament",
              position: 1,
              contextLabel: "Argumente",
              moduleId: "module-2",
              material: { id: "material-2", title: "Positionen im Parlament", kind: "markdown" as const, body_md: "Text" }
            },
            {
              key: "task:task-2",
              kind: "task" as const,
              title: "Aufgabe 2",
              position: 2,
              contextLabel: "Argumente",
              moduleId: "module-2",
              task: { id: "task-2", instruction_md: "Aufgabe", criteria: [], kind: "native" as const, has_submission: true }
            }
          ]
        }
      ]
    };
    render(LearnerContentWorkspace, { props });

    await fireEvent.click(screen.getByRole("button", { name: /Positionen im Parlament/ }));
    expect(onAddContextReference).toHaveBeenCalledWith(
      expect.objectContaining({ key: "material:material-2", kind: "material", moduleId: "module-2" })
    );
    await fireEvent.click(screen.getByRole("button", { name: /Eigene frühere Abgabe Aufgabe 2/ }));
    expect(onAddContextReference).toHaveBeenCalledWith(
      expect.objectContaining({ key: "submission:task-2", kind: "submission", taskId: "task-2" })
    );
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
});
