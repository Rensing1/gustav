<script lang="ts">
  import type { Snippet } from "svelte";
  import { fitGraphToScreen } from "$lib/graph/graph-presentation";

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
    contextBar,
    contextOpen = false,
    inspectorOpen = false,
    embedded = false,
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
    contextBar?: Snippet;
    contextOpen?: boolean;
    inspectorOpen?: boolean;
    embedded?: boolean;
    canvas?: Snippet;
    inspector?: Snippet;
  } = $props();
</script>

<div
  class:teacher-graph-workspace-frame--with-context={contextOpen && Boolean(contextBar)}
  class="teacher-graph-workspace-frame"
>
  <PageActionHead
    {backHref}
    {backLabel}
    {title}
    {copy}
    actions={headerActions}
  />

  <div class="teacher-graph-workspace-frame__commandbar">
    <TeacherGraphCommandBar actions={commandBarActions} popovers={commandBarPopovers} />
  </div>

  <section
    use:fitGraphToScreen
    class:teacher-flow-workspace--with-context={contextOpen && Boolean(contextBar)}
    class:teacher-flow-workspace--with-inspector={inspectorOpen}
    class:teacher-flow-workspace--embedded={embedded}
    class="teacher-flow-workspace teacher-flow-shell"
  >
    {#if contextOpen && contextBar}
      <div class="teacher-flow-workspace__context">
        {@render contextBar()}
      </div>
    {/if}

    <div class="teacher-flow-workspace__canvas" tabindex="-1" aria-label="Lernweg-Graph">
      {@render canvas?.()}
    </div>

    {#if inspectorOpen && inspector}
      {@render inspector()}
    {/if}
  </section>
</div>
