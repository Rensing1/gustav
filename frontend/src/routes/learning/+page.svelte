<script lang="ts">
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>Lernraum | GUSTAV</title>
</svelte:head>

<div class="workspace-page learning-home">
  <section class="learning-home-header">
    <h2>Meine Klassen</h2>
  </section>

  {#if data.home?.courses?.length}
    <ul class="learning-home-list">
      {#each data.home.courses as course}
        <li>
          <a class="learning-home-card" href={course.href}>
            <strong>{course.title}</strong>
            <span class="learning-home-open">Öffnen</span>
          </a>
        </li>
      {/each}
    </ul>
  {:else}
    <section class="workspace-panel learning-home-empty">
      <p class="workspace-empty">Noch keine Klassen sichtbar.</p>
    </section>
  {/if}
</div>
