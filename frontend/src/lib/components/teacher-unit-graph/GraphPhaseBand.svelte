<script lang="ts">
  import { goto } from "$app/navigation";
  import type { NodeProps } from "@xyflow/svelte";
  import { getContext } from "svelte";

  import type { TeacherFlowNodeData } from "$lib/graph/teacher-unit-flow";
  import {
    TEACHER_GRAPH_SELECTION_CONTEXT,
    type TeacherGraphSelectionHandler
  } from "./selection-context";

  let { id, data, selected = false }: NodeProps & { data: TeacherFlowNodeData; selected?: boolean } = $props();
  const selectGraphItem = getContext<TeacherGraphSelectionHandler | undefined>(TEACHER_GRAPH_SELECTION_CONTEXT);

  function editorialPhaseKicker(kicker: string): string {
    const match = kicker.match(/(\d+)/);
    if (!match) {
      return kicker.toUpperCase();
    }

    const phaseNumber = Number.parseInt(match[1] ?? "0", 10);
    return `PHASE ${String(phaseNumber).padStart(2, "0")}`;
  }

  function phaseHref(): string | null {
    return data.selectHref ?? null;
  }

  function selectPhase(event: MouseEvent) {
    const href = phaseHref();
    if (!href) return;
    event.preventDefault();
    event.stopPropagation();
    if (selectGraphItem) {
      selectGraphItem("phase", data.phaseId ?? id.replace(/^phase:/, ""));
      return;
    }
    void goto(`${window.location.pathname}${href}`, { keepFocus: true, noScroll: true });
  }

</script>

<div class:teacher-flow-phase-band--selected={selected} class="teacher-flow-phase-band">
  {#if phaseHref()}
    <a class="teacher-flow-phase-band__label nodrag nopan" href={phaseHref() ?? undefined} onclick={selectPhase}>
      <span class="teacher-flow-phase-band__kicker">{editorialPhaseKicker(data.kicker)}</span>
      <strong class="teacher-flow-phase-band__title">{data.title}</strong>
    </a>
  {:else}
    <div class="teacher-flow-phase-band__label">
      <span class="teacher-flow-phase-band__kicker">{editorialPhaseKicker(data.kicker)}</span>
      <strong class="teacher-flow-phase-band__title">{data.title}</strong>
    </div>
  {/if}
</div>
