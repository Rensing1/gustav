<script lang="ts">
  import LearnerMaterialRow from "$lib/components/learning-unit/LearnerMaterialRow.svelte";
  import type { LearnerMaterialContextModule } from "$lib/learning-unit/workspace";

  let {
    modules = [],
    focusedModuleId = null,
    expandedModuleMaterialKeys = {},
    onToggleMaterial = null,
    onOpenReference = null
  }: {
    modules?: LearnerMaterialContextModule[];
    focusedModuleId?: string | null;
    expandedModuleMaterialKeys?: Record<string, string[]>;
    onToggleMaterial?: ((moduleId: string, referenceKey: string) => void) | null;
    onOpenReference?: ((referenceKey: string) => void | Promise<void>) | null;
  } = $props();

  function focusedModule(): LearnerMaterialContextModule | null {
    return modules.find((module) => module.id === focusedModuleId)
      ?? modules.find((module) => module.current)
      ?? modules[0]
      ?? null;
  }

  function materialItems() {
    return focusedModule()?.items.filter((item) => item.kind === "material" && item.material) ?? [];
  }

  function materialExpanded(moduleId: string, referenceKey: string, index: number): boolean {
    const stored = expandedModuleMaterialKeys[moduleId];
    return stored ? stored.includes(referenceKey) : index === 0;
  }

</script>

<section class="learner-focused-materials" aria-label="Materialien zur Aufgabe">
  <h3>Materialien</h3>

  {#if materialItems().length}
    <div class="learner-focused-materials__list">
      {#each materialItems() as item, index (item.key)}
        <LearnerMaterialRow
          {item}
          expanded={materialExpanded(focusedModule()!.id, item.key, index)}
          onToggle={(referenceKey) => onToggleMaterial?.(focusedModule()!.id, referenceKey)}
          {onOpenReference}
        />
      {/each}
    </div>
  {:else}
    <p class="workspace-note">Für diese Aufgabe sind keine zusätzlichen Materialien hinterlegt.</p>
  {/if}
</section>
