<script lang="ts">
  import { SvelteFlow } from "@xyflow/svelte";
  import { fitGraphToScreen, graphAriaLabels } from "$lib/graph/graph-presentation";
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
    edges,
    busy = false,
    error = null,
    onRetry
  }: {
    graph: LearningUnitGraph | null;
    nodes: LearningFlowNode[];
    edges: TeacherFlowEdge[];
    busy?: boolean;
    error?: string | null;
    onRetry?: () => void;
  } = $props();

  const nodeTypes = {
    unitNode: LearningGraphNode,
    phaseBand: GraphPhaseBand
  };

  const edgeTypes = {
    teacherEdge: TeacherGraphEdge
  };
</script>

<GraphStageFrame chromeless eyebrow="Lernpfad" title="Lernpfad">
  {#snippet children()}
    <section use:fitGraphToScreen class="learning-unit-stage learning-unit-stage--graph teacher-flow-workspace teacher-flow-shell learning-flow-shell">
      {#if error}
        <div role="alert">
          <p>{error}</p>
          <button class="workspace-link-action" type="button" onclick={onRetry}>Erneut versuchen</button>
        </div>
      {:else if busy && nodes.length === 0}
        <p role="status">Lernpfad wird aufgebaut …</p>
      {:else if graph && nodes.length > 0}
        <SvelteFlow
          ariaLabelConfig={graphAriaLabels}
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
            storageKey={`gustav:learner-graph:${graph.unit.id}:viewport`}
            initialNodeId={nodes.find((node) => node.selected)?.id ?? nodes.find((node) => node.type === "phaseBand")?.id ?? null}
            showInteractionToggle={false}
          />
        </SvelteFlow>
      {:else if graph}
        <p class="learning-unit-empty-copy">Der Lernpfad enthält noch keine Module.</p>
      {:else}
        <p class="learning-unit-empty-copy">Der Graph konnte nicht geladen werden.</p>
      {/if}
    </section>
  {/snippet}
</GraphStageFrame>
