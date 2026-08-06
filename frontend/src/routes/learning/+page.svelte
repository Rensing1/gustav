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
  <h2>Aktuelle Kurse</h2>
  {#if data.home?.current_courses?.length}
    <QuietList>
      {#each data.home.current_courses as course}
        <QuietListEntry href={course.href} title={course.title} />
      {/each}
    </QuietList>
  {:else}
    <section class="workspace-panel learning-home-empty">
      <p class="workspace-empty">Noch keine Klassen sichtbar.</p>
    </section>
  {/if}

  {#if data.home?.past_courses?.length}
    <section class="learning-home-past">
      <h2>Vergangene Kurse</h2>
      <QuietList>
        {#each data.home.past_courses as course}
          <QuietListEntry
            href={course.href}
            title={course.title}
            meta={course.school_year_start ? `${course.school_year_start}/${String(course.school_year_start + 1).slice(-2)}` : ""}
          />
        {/each}
      </QuietList>
    </section>
  {/if}
</div>
