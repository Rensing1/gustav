<script lang="ts">
  import { SvelteFlow } from "@xyflow/svelte";
  import "@xyflow/svelte/dist/style.css";

  import GraphPhaseBand from "$lib/components/teacher-unit-graph/GraphPhaseBand.svelte";
  import GraphStageFrame from "$lib/components/ui/GraphStageFrame.svelte";
  import GraphViewportControls from "$lib/components/ui/GraphViewportControls.svelte";
  import TeacherGraphEdge from "$lib/components/teacher-unit-graph/TeacherGraphEdge.svelte";
  import LearningGraphNode from "$lib/components/learning-unit/LearningGraphNode.svelte";
  import type { LearningFlowNode } from "$lib/graph/learning-unit-flow";
  import type { TeacherFlowEdge } from "$lib/graph/teacher-unit-flow";
  import type { LearningUnitGraph } from "$lib/types/learning";

  let {
    graph,
    nodes,
    edges
  }: {
    graph: LearningUnitGraph | null;
    nodes: LearningFlowNode[];
    edges: TeacherFlowEdge[];
  } = $props();

  const nodeTypes = {
    unitNode: LearningGraphNode,
    phaseBand: GraphPhaseBand
  };

  const edgeTypes = {
    teacherEdge: TeacherGraphEdge
  };
</script>

<GraphStageFrame chromeless eyebrow="Graph-Stage" title="Lernpfad" copy="Taskfläche zuerst, Graph daraus abgeleitet.">
  {#snippet children()}
    <section class="learning-unit-stage learning-unit-stage--graph teacher-flow-workspace teacher-flow-shell learning-flow-shell">
      {#if graph}
        <SvelteFlow
          bind:nodes={nodes}
          bind:edges={edges}
          class="teacher-flow-canvas"
          {nodeTypes}
          {edgeTypes}
          minZoom={0.1}
          maxZoom={1.26}
          elementsSelectable={false}
          nodesFocusable={false}
          panOnDrag={true}
          selectNodesOnDrag={false}
          nodesDraggable={false}
          nodesConnectable={false}
        >
          <GraphViewportControls
            initialNodeId={nodes.find((node) => node.selected)?.id ?? nodes.find((node) => node.type === "phaseBand")?.id ?? null}
            showInteractionToggle={false}
          />
        </SvelteFlow>
      {:else}
        <p class="learning-unit-empty-copy">Der Graph konnte nicht geladen werden.</p>
      {/if}
    </section>
  {/snippet}
</GraphStageFrame>
