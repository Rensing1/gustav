<script lang="ts">
  import QuietList from "$lib/components/ui/QuietList.svelte";
  import QuietListEntry from "$lib/components/ui/QuietListEntry.svelte";
  import PageActionHead from "$lib/components/ui/PageActionHead.svelte";
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>{data.courseTitle} | GUSTAV</title>
</svelte:head>

<div class="workspace-page learning-home learning-course-home">
  <PageActionHead backHref="/learning" backLabel="Zurück zum Lernraum" title={data.courseTitle}>
    {#snippet actions()}
      <a class="workspace-link-action" href={`/learning/courses/${data.courseId}/archive`}>Meine Lernleistung &amp; Export</a>
    {/snippet}
  </PageActionHead>
  {#if data.units.length}
    <QuietList>
      {#each data.units as row}
        <QuietListEntry
          href={`/learning/courses/${data.courseId}/units/${row.unit.id}`}
          title={row.unit.title}
        />
      {/each}
    </QuietList>
  {:else}
    <section class="workspace-panel learning-home-empty">
      <p class="workspace-empty">Noch keine Lerneinheiten sichtbar.</p>
    </section>
  {/if}
</div>
