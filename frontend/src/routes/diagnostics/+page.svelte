<script lang="ts">
  import type { PageData } from "./$types";
  let { data }: { data: PageData } = $props();
  let selectedCourse = $state("");
  const course = $derived(data.courses.find((item) => item.id === selectedCourse));
</script>

<svelte:head><title>Diagnostik | GUSTAV</title></svelte:head>

<div class="workspace-page">
  <section class="workspace-panel workspace-panel--flat workspace-section diagnostics-panel">
    <p class="workspace-kicker">Diagnostik</p>
    <h2>Kursmatrix öffnen</h2>
    <p class="workspace-note">Wähle einen Kurs, um die Abgaben seiner Lernenden im Überblick zu sehen.</p>
    {#if data.courses.length}
      <label class="workspace-field">
        <span>Kurs</span>
        <select bind:value={selectedCourse}>
          <option value="">Kurs wählen</option>
          {#each data.courses as item}<option value={item.id}>{item.title}</option>{/each}
        </select>
      </label>
      {#if course}
        <a class="workspace-link-action workspace-link-action--primary" href={`/diagnostics/courses/${course.id}`}>Kursmatrix öffnen</a>
      {:else}
        <p class="workspace-note">Wähle zuerst einen Kurs.</p>
      {/if}
    {:else}
      <p class="workspace-empty">Du hast noch keine aktiven Kurse.</p>
      <a class="workspace-link-action" href="/teaching/courses">Kurse öffnen</a>
    {/if}
  </section>
</div>
