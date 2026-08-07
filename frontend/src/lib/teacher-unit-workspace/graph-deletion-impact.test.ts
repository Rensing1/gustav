import { describe, expect, it } from "vitest";

import type { TeacherUnitWorkspaceView } from "$lib/types/home";

import { graphDeletionFallback, graphDeletionImpact } from "./graph-deletion-impact";

const workspace = {
  graph: {
    kind: "modular",
    phases: [
      {
        id: "phase-1",
        title: "Grundlagen",
        position: 1,
        modules: [
          { id: "module-1", title: "Start", phase_id: "phase-1", materials_count: 2, tasks_count: 3 },
          { id: "module-2", title: "Übung", phase_id: "phase-1", materials_count: 4, tasks_count: 5 }
        ]
      },
      {
        id: "phase-2",
        title: "Transfer",
        position: 2,
        modules: [
          { id: "module-3", title: "Ziel", phase_id: "phase-2", materials_count: 1, tasks_count: 1 }
        ]
      }
    ],
    edges: [
      { from: "module-1", to: "module-2" },
      { from: "module-2", to: "module-3" },
      { from: "module-3", to: "module-1" }
    ]
  }
} as TeacherUnitWorkspaceView;

describe("graphDeletionImpact", () => {
  it("sums every cascading consequence for a phase", () => {
    expect(graphDeletionImpact(workspace, { kind: "phase", id: "phase-1" })).toEqual({
      kind: "phase",
      id: "phase-1",
      title: "Grundlagen",
      modulesCount: 2,
      materialsCount: 6,
      tasksCount: 8,
      connectionsCount: 3
    });
  });

  it("counts only the selected module and its touching connections", () => {
    expect(graphDeletionImpact(workspace, { kind: "module", id: "module-1" })).toEqual({
      kind: "module",
      id: "module-1",
      title: "Start",
      modulesCount: 1,
      materialsCount: 2,
      tasksCount: 3,
      connectionsCount: 2
    });
  });

  it("chooses a stable neighbouring graph target after deletion", () => {
    expect(graphDeletionFallback(workspace, { kind: "module", id: "module-1" })).toEqual({
      kind: "module",
      id: "module-2"
    });
    expect(graphDeletionFallback(workspace, { kind: "module", id: "module-2" })).toEqual({
      kind: "module",
      id: "module-1"
    });
    expect(graphDeletionFallback(workspace, { kind: "phase", id: "phase-1" })).toEqual({
      kind: "phase",
      id: "phase-2"
    });
  });
});
