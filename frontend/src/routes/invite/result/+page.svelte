<script lang="ts">
  import type { PageData } from "./$types";
  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>Kurseinladung | GUSTAV</title>
  <meta name="referrer" content="no-referrer" />
</svelte:head>

<main class="invite-result">
  <section>
    {#if data.reason === "removed"}
      <h1>Der Wiedereintritt ist mit diesem Link nicht möglich</h1>
      <p>Bitte deine Lehrkraft um einen neu erzeugten Klassenlink.</p>
    {:else if data.reason === "temporary"}
      <h1>Der Beitritt konnte gerade nicht abgeschlossen werden</h1>
      <p>Versuche es bitte in wenigen Minuten noch einmal.</p>
    {:else}
      <h1>Diese Einladung ist nicht mehr gültig</h1>
      <p>Bitte deine Lehrkraft um einen neuen Klassenlink.</p>
    {/if}
    <a href="/">Zur Startseite</a>
  </section>
</main>

<style>
  .invite-result { display: grid; min-height: 70vh; padding: 2rem; place-items: center; }
  .invite-result section { max-width: 38rem; text-align: center; }
</style>
