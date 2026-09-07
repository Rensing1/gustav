<script lang="ts">
  import { onMount, untrack } from "svelte";
  import { ControlButton, Controls, useNodesInitialized, useSvelteFlow, useViewportInitialized } from "@xyflow/svelte";

  export type GraphViewportController = {
    focusNode: (nodeId?: string | null) => void;
    showAll: () => void;
  };

  let {
    initialNodeId = null,
    onControllerReady,
    showInteractionToggle = true
  }: {
    initialNodeId?: string | null;
    onControllerReady?: ((controller: GraphViewportController) => void) | null;
    showInteractionToggle?: boolean;
  } = $props();

  const flow = useSvelteFlow();
  const nodesInitialized = useNodesInitialized();
  const viewportInitialized = useViewportInitialized();
  let initialFocusApplied = $state(false);

  function focusNode(nodeId: string | null = initialNodeId, attempt = 0) {
    if (!nodeId) return;
    const node = flow.getNode(nodeId);
    if (!node) {
      if (attempt < 10) requestAnimationFrame(() => focusNode(nodeId, attempt + 1));
      return;
    }
    void flow.fitView({ nodes: [node], padding: 0.34, minZoom: 0.82, maxZoom: 1.02, duration: 180 });
  }

  async function showAll() {
    const allNodes = flow.getNodes();
    const phaseBands = allNodes.filter((node) => node.type === "phaseBand");
    await flow.fitView({
      nodes: phaseBands.length > 0 ? phaseBands : allNodes,
      padding: 0.2,
      // Overview may shrink below reading size; the focus action restores it.
      minZoom: 0.1,
      maxZoom: 0.92,
      duration: 0
    });
  }

  const controller: GraphViewportController = { focusNode, showAll };

  onMount(() => {
    onControllerReady?.(controller);
  });

  // Role adapters can deliver nodes after mount. Focus once they are measured,
  // then preserve the user's camera when selection or progress changes.
  $effect(() => {
    if (!initialFocusApplied && initialNodeId && nodesInitialized.current && viewportInitialized.current) {
      initialFocusApplied = true;
      untrack(() => focusNode(initialNodeId));
    }
  });
</script>

{#snippet additionalControls()}
  <ControlButton onclick={showAll} title="Gesamtansicht" aria-label="Gesamtansicht">
    <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16">
      <path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5" fill="none" stroke="currentColor" stroke-width="2" />
    </svg>
  </ControlButton>
  <ControlButton onclick={() => focusNode()} title="Auswahl fokussieren" aria-label="Auswahl fokussieren" disabled={!initialNodeId}>
    <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16">
      <circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="2" />
      <path d="M12 2v4M12 18v4M2 12h4M18 12h4" fill="none" stroke="currentColor" stroke-width="2" />
    </svg>
  </ControlButton>
{/snippet}

<Controls position="bottom-right" showFitView={false} showLock={showInteractionToggle} after={additionalControls} />
