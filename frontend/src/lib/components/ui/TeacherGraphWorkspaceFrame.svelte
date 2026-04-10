<script lang="ts">
  import type { Snippet } from "svelte";

  import TeacherGraphCommandBar, {
    type TeacherGraphCommandBarAction
  } from "$lib/components/teacher-unit-graph/TeacherGraphCommandBar.svelte";

  import PageActionHead from "./PageActionHead.svelte";

  let {
    backHref,
    backLabel,
    title,
    copy,
    headerActions,
    commandBarActions,
    commandBarPopovers,
    inspectorOpen = false,
    canvas,
    inspector
  }: {
    backHref: string;
    backLabel: string;
    title: string;
    copy: string;
    headerActions?: Snippet;
    commandBarActions: TeacherGraphCommandBarAction[];
    commandBarPopovers?: Snippet;
    inspectorOpen?: boolean;
    canvas?: Snippet;
    inspector?: Snippet;
  } = $props();
</script>

<PageActionHead
  {backHref}
  {backLabel}
  {title}
  {copy}
  actions={headerActions}
>
  {#snippet secondary()}
    <TeacherGraphCommandBar actions={commandBarActions} popovers={commandBarPopovers} />
  {/snippet}
</PageActionHead>

<section class:teacher-flow-workspace--with-inspector={inspectorOpen} class="teacher-flow-workspace teacher-flow-shell">
  <div class="teacher-flow-workspace__canvas">
    {@render canvas?.()}
  </div>

  {#if inspectorOpen && inspector}
    {@render inspector()}
  {/if}
</section>
