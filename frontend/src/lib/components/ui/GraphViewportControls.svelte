<script lang="ts">
  import { onMount, untrack } from "svelte";
  import { ControlButton, Controls, useNodesInitialized, useSvelteFlow, useViewportInitialized, useViewport } from "@xyflow/svelte";
  import { readViewport, writeViewport } from "$lib/graph/viewport-memory";
  import { graphFocusNodes, orientationForViewport } from "$lib/graph/graph-presentation";

  export type GraphViewportController = {
    focusNode: (nodeId?: string | null) => void;
    showAll: () => void;
  };

  let {
    initialNodeId = null,
    onControllerReady,
    showInteractionToggle = true,
    storageKey = null
  }: {
    initialNodeId?: string | null;
    onControllerReady?: ((controller: GraphViewportController) => void) | null;
    showInteractionToggle?: boolean;
    storageKey?: string | null;
  } = $props();

  const flow = useSvelteFlow();
  const nodesInitialized = useNodesInitialized();
  const viewportInitialized = useViewportInitialized();
  const viewport = useViewport();
  let initialFocusApplied = $state(false);
  let cameraReady = $state(false);
  let viewportError = $state<string | null>(null);
  let layoutFrame = 0;

  async function adjustViewport(action: () => Promise<unknown>) {
    viewportError = null;
    try {
      await action();
    } catch {
      viewportError = "Die Graphansicht konnte nicht ausgerichtet werden. Bitte versuche es erneut.";
    }
  }

  function focusNode(nodeId: string | null = initialNodeId, attempt = 0) {
    if (!nodeId) return;
    const nodes = graphFocusNodes(nodeId, flow.getNodes());
    if (nodes.length === 0) {
      if (attempt < 10) requestAnimationFrame(() => focusNode(nodeId, attempt + 1));
      return;
    }
    void adjustViewport(() => flow.fitView({ nodes, padding: 0.24, minZoom: 0.82, maxZoom: 1.02, duration: 180 }));
  }

  function afterStableGraphLayout(action: () => void) {
    cancelAnimationFrame(layoutFrame);
    layoutFrame = requestAnimationFrame(() => {
      layoutFrame = requestAnimationFrame(action);
    });
  }

  async function showAll() {
    const allNodes = flow.getNodes();
    const phaseBands = allNodes.filter((node) => node.type === "phaseBand");
    await adjustViewport(() => flow.fitView({
      nodes: phaseBands.length > 0 ? phaseBands : allNodes,
      padding: 0.2,
      // Overview may shrink below reading size; the focus action restores it.
      minZoom: 0.1,
      maxZoom: 0.92,
      duration: 0
    }));
  }

  const controller: GraphViewportController = { focusNode, showAll };

  onMount(() => {
    onControllerReady?.(controller);
    let orientation = orientationForViewport(window.innerWidth, window.innerHeight);
    const handleResize = () => {
      const nextOrientation = orientationForViewport(window.innerWidth, window.innerHeight);
      if (nextOrientation === orientation) return;
      orientation = nextOrientation;
      afterStableGraphLayout(() => focusNode());
    };
    window.addEventListener("resize", handleResize);
    return () => {
      cancelAnimationFrame(layoutFrame);
      window.removeEventListener("resize", handleResize);
    };
  });

  // Role adapters can deliver nodes after mount. Focus once they are measured,
  // then preserve the user's camera when selection or progress changes.
  $effect(() => {
    if (!initialFocusApplied && initialNodeId && nodesInitialized.current && viewportInitialized.current) {
      initialFocusApplied = true;
      untrack(() => {
        afterStableGraphLayout(() => {
          const saved = storageKey ? readViewport(sessionStorage, storageKey) : null;
          if (saved) void adjustViewport(() => flow.setViewport(saved));
          else focusNode(initialNodeId);
          cameraReady = true;
        });
      });
    }
  });

  $effect(() => {
    if (storageKey && cameraReady) writeViewport(sessionStorage, storageKey, viewport.current);
  });
</script>

{#if viewportError}
  <p class="graph-viewport-error nodrag nopan" role="alert">{viewportError}</p>
{/if}

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
