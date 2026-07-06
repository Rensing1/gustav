import { describe, expect, it } from "vitest";

import type { TeacherUnitWorkspaceView } from "$lib/types/home";

import {
  deriveEdgeSelection,
  deriveModuleSelection,
  workspaceGraphSignature
} from "./view-state";


function modularWorkspace(): TeacherUnitWorkspaceView {
  return {
    user: { sub: "teacher-1", name: "Lehrkraft", role: "teacher", roles: ["teacher"] },
    unit: {
      id: "unit-1",
      title: "Modulare Einheit",
      summary: null,
      unit_type: "modular",
      edit_href: "/teaching/units/unit-1"
    },
    counts: {
      sections_count: 0,
      phases_count: 1,
      modules_count: 2,
      courses_count: 0
    },
    graph: {
      kind: "modular",
      phases: [
        {
          id: "phase-1",
          title: "Phase 1",
          position: 1,
          modules: [
            {
              id: "module-1",
              title: "Modul 1",
              phase_id: "phase-1",
              position_in_phase: 1,
              required_prereq_count: 0,
              materials_count: 2,
              tasks_count: 1,
              editor_href: "/nodes/module-1"
            },
            {
              id: "module-2",
              title: "Modul 2",
              phase_id: "phase-1",
              position_in_phase: 2,
              required_prereq_count: 1,
              materials_count: 0,
              tasks_count: 3,
              editor_href: "/nodes/module-2"
            }
          ]
        }
      ],
      edges: [{ from: "module-1", to: "module-2" }]
    },
    selection: { kind: "none" }
  };
}


describe("teacher unit workspace view-state helpers", () => {
  it("includes module ordering fields in the graph signature", () => {
    const first = modularWorkspace();
    const second = modularWorkspace();
    second.graph.phases?.[0]?.modules.reverse();

    expect(workspaceGraphSignature(first)).not.toEqual(workspaceGraphSignature(second));
  });

  it("derives module selections from the workspace graph", () => {
    const selection = deriveModuleSelection(modularWorkspace(), "module-2");

    expect(selection).toEqual({
      kind: "module",
      module: {
        id: "module-2",
        title: "Modul 2",
        phase_id: "phase-1",
        position_in_phase: 2,
        required_prereq_count: 1,
        materials_count: 0,
        tasks_count: 3,
        editor_href: "/nodes/module-2"
      }
    });
  });

  it("marks edge selections as existing only when the graph contains the edge", () => {
    expect(deriveEdgeSelection(modularWorkspace(), "module-1", "module-2")).toMatchObject({
      kind: "edge",
      edge: { exists: true }
    });
    expect(deriveEdgeSelection(modularWorkspace(), "module-2", "module-1")).toMatchObject({
      kind: "edge",
      edge: { exists: false }
    });
  });
});
