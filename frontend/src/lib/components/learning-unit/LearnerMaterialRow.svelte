<script lang="ts">
  import LearningReferenceDocument from "$lib/components/learning-unit/LearningReferenceDocument.svelte";
  import type { LearnerMaterialContextModule } from "$lib/learning-unit/workspace";

  let {
    item,
    expanded = false,
    onToggle = null,
    onOpenReference = null
  }: {
    item: LearnerMaterialContextModule["items"][number];
    expanded?: boolean;
    onToggle?: ((referenceKey: string) => void) | null;
    onOpenReference?: ((referenceKey: string) => void | Promise<void>) | null;
  } = $props();
</script>

<LearningReferenceDocument
  referenceKey={item.key}
  label={null}
  title={item.title}
  material={item.material}
  {expanded}
  compact={true}
  {onToggle}
  onOpenReader={onOpenReference}
/>
