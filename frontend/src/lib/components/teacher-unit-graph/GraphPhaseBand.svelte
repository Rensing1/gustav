<script lang="ts">
  import type { NodeProps } from "@xyflow/svelte";

  import type { TeacherFlowNodeData } from "$lib/graph/teacher-unit-flow";

  let { data, selected = false }: NodeProps & { data: TeacherFlowNodeData; selected?: boolean } = $props();

  function editorialPhaseKicker(kicker: string): string {
    const match = kicker.match(/(\d+)/);
    if (!match) {
      return kicker.toUpperCase();
    }

    const phaseNumber = Number.parseInt(match[1] ?? "0", 10);
    return `PHASE ${String(phaseNumber).padStart(2, "0")}`;
  }

  function phaseHref(): string | null {
    return data.quickHref ?? data.selectHref ?? null;
  }
</script>

<div class:teacher-flow-phase-band--selected={selected} class="teacher-flow-phase-band">
  {#if phaseHref()}
    <a class="teacher-flow-phase-band__label nodrag nopan" href={phaseHref() ?? undefined}>
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
