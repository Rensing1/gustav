<script lang="ts">
  import QuietList from "$lib/components/ui/QuietList.svelte";
  import QuietListEntry from "$lib/components/ui/QuietListEntry.svelte";
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>Lernraum | GUSTAV</title>
</svelte:head>

<div class="workspace-page learning-home">
  {#if data.home?.courses?.length}
    <QuietList>
      {#each data.home.courses as course}
        <QuietListEntry href={course.href} title={course.title} />
      {/each}
    </QuietList>
  {:else}
    <section class="workspace-panel learning-home-empty">
      <p class="workspace-empty">Noch keine Klassen sichtbar.</p>
    </section>
  {/if}
</div>
