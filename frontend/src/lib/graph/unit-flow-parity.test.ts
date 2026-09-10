import { describe, expect, it, vi } from "vitest";

import type { TeacherUnitWorkspaceView } from "$lib/types/home";
import type { LearningUnitGraph } from "$lib/types/learning";
import type { SessionBootstrapUser } from "$lib/types/session-bootstrap";
import { buildLearningUnitFlow } from "./learning-unit-flow";
import { buildTeacherUnitFlow, type TeacherFlowEdge, type TeacherFlowNode } from "./teacher-unit-flow";

const user = { sub: "test-learner", roles: ["student"], name: "Test" } as SessionBootstrapUser;

function graphFixture(): LearningUnitGraph {
  return {
    unit: { id: "unit", title: "Gemeinsamer Lernpfad", unit_type: "modular" },
    phases: [1, 2, 3].map((position) => ({ id: `phase-${position}`, position, title: `Phase ${position}` })),
    modules: ["a", "b", "c", "d", "practice", "last"].map((id, index) => ({
      id, title: id, phase_id: index < 4 ? "phase-1" : "phase-2",
      position_in_phase: index < 4 ? index + 1 : index - 3,
      module_kind: id === "practice" ? "practice" : "learning",
      due_tasks_count: 1, required_prereq_count: 0, prereq_done: 0, prereq_required: 0,
      tasks_done: 0, tasks_total: 1, materials_count: 1,
      status: index === 0 ? "done" : index === 3 ? "locked" : "open"
    })),
    edges: [
      { from: "a", to: "b" }, { from: "a", to: "c" },
      { from: "b", to: "d" }, { from: "c", to: "d" },
      { from: "d", to: "last" }, { from: "d", to: "practice" }
    ]
  };
}

function teacherFixture(graph: LearningUnitGraph): TeacherUnitWorkspaceView {
  return {
    user, unit: { ...graph.unit, edit_href: "/teaching/units/unit" },
    counts: { sections_count: 0, phases_count: graph.phases.length, modules_count: graph.modules.length, courses_count: 1 },
    selection: { kind: "none" },
    graph: {
      kind: "modular", edges: graph.edges,
      phases: graph.phases.map((phase) => ({
        ...phase,
        modules: graph.modules.filter((module) => module.phase_id === phase.id).map((module) => ({
          ...module, tasks_count: module.tasks_total, editor_href: `/teaching/units/unit/nodes/${module.id}`
        }))
      }))
    }
  };
}

function geometry(flow: { nodes: TeacherFlowNode[]; edges: TeacherFlowEdge[] }) {
  return {
    nodes: flow.nodes.map(({ id, position, width, height, parentId }) => ({ id, position, width, height, parentId }))
      .sort((a, b) => a.id.localeCompare(b.id)),
    edges: flow.edges.map(({ id, source, target, sourceHandle, targetHandle, pathOptions }) => ({
      id, source, target, sourceHandle, targetHandle, pathOptions
    })).sort((a, b) => a.id.localeCompare(b.id))
  };
}

describe("one graph geometry for both roles", () => {
  it("explains locked prerequisites without inventing missing conditions", async () => {
    const graph = graphFixture();
    const locked = graph.modules.find((module) => module.id === "d")!;
    locked.prereq_required = 2;
    locked.prereq_done = 1;
    const flow = await buildLearningUnitFlow(graph, user, [], vi.fn());
    expect(flow.nodes.find((node) => node.id === "d")!.data.progressLabel).toBe("Gesperrt");
    expect(flow.nodes.find((node) => node.id === "d")!.data.materialsLabel).toBe("1/2 Voraussetzungen erfüllt");
    locked.prereq_required = 0;
    const unknown = await buildLearningUnitFlow(graph, user, [], vi.fn());
    expect(unknown.nodes.find((node) => node.id === "d")!.data.materialsLabel).toBe("Freischaltbedingungen nicht verfügbar");
  });
  it("preserves branches, joins, cross-phase edges, practice modules and empty phases", async () => {
    const graph = graphFixture();
    const teacher = await buildTeacherUnitFlow(teacherFixture(graph));
    const learner = await buildLearningUnitFlow(graph, user, ["a"], vi.fn());
    expect(geometry(learner)).toEqual(geometry(teacher));
    expect(learner.nodes).toHaveLength(9);
    expect(learner.edges).toHaveLength(6);
    expect(teacher.edges[0].ariaLabel).toMatch(/^Verbindung von .+ nach .+$/);
  });

  it("uses stored positions and stable edge lanes, not incoming array order", async () => {
    const graph = graphFixture();
    const expected = geometry(await buildTeacherUnitFlow(teacherFixture(graph)));
    const shuffled = {
      ...graph, phases: [...graph.phases].reverse(), modules: [...graph.modules].reverse(), edges: [...graph.edges].reverse()
    };
    const before = JSON.stringify(shuffled);
    expect(geometry(await buildTeacherUnitFlow(teacherFixture(shuffled)))).toEqual(expected);
    expect(geometry(await buildLearningUnitFlow(shuffled, user, [], vi.fn()))).toEqual(expected);
    expect(JSON.stringify(shuffled)).toBe(before);
  });

  it("keeps progress and open tabs out of geometry and never offers teacher actions", async () => {
    const graph = graphFixture();
    const open = vi.fn();
    const flow = await buildLearningUnitFlow(graph, user, ["a", "d"], open);
    const expected = geometry(flow);
    for (const node of flow.nodes) {
      expect(node.draggable).toBe(false);
      for (const field of ["selectHref", "editorHref", "createHref", "quickHref"] as const) {
        expect(node.data[field]).toBeNull();
      }
      if (node.data.kind !== "module") continue;
      expect(node.data.connectable).toBe(false);
      if (node.data.status === "locked") {
        expect(node.data.onSelect).toBeNull();
        expect(node.selected).toBe(false);
      } else {
        node.data.onSelect?.();
        expect(open).toHaveBeenLastCalledWith(node.id);
      }
    }
    const updated = { ...graph, modules: graph.modules.map((module) => ({ ...module, status: "done" as const, tasks_done: 1 })) };
    expect(geometry(await buildLearningUnitFlow(updated, user, ["b", "c"], open))).toEqual(expected);
  });
});
