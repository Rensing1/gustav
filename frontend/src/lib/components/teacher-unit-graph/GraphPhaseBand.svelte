<script lang="ts">
  import type { NodeProps } from "@xyflow/svelte";

  import type { TeacherFlowNodeData } from "$lib/graph/teacher-unit-flow";

  let { data, selected = false }: NodeProps & { data: TeacherFlowNodeData; selected?: boolean } = $props();

  function compactPhaseKicker(kicker: string): string {
    const match = kicker.match(/(\d+)/);
    if (!match) {
      return kicker;
    }

    return `Phase ${String(Number.parseInt(match[1] ?? "0", 10))}`;
  }

  function phaseLabel(): string {
    return `${compactPhaseKicker(data.kicker)}: ${data.title}`;
  }
</script>

<div class:teacher-flow-phase-band--selected={selected} class="teacher-flow-phase-band">
  <div class="teacher-flow-phase-band__rule" aria-hidden="true"></div>
  <div class="teacher-flow-phase-band__label">
    <strong>{phaseLabel()}</strong>
  </div>
</div>
