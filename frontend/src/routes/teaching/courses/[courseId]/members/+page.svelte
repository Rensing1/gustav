<script lang="ts">
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>Mitglieder | GUSTAV</title>
</svelte:head>

<section class="panel">
  <p class="kicker">Teaching</p>
  <h2>Mitglieder in {data.home?.course?.title ?? "diesem Kurs"}</h2>
  <p class="lead">
    Die Kursmitgliedschaft ist jetzt als SvelteKit-Seite erreichbar und nicht
    mehr nur ueber die alte FastAPI-SSR-Strecke.
  </p>

  <article class="card">
    {#if data.home?.members?.length}
      <ul class="member-list">
        {#each data.home.members as member}
          <li>
            <strong>{member.name}</strong>
            <span>{member.sub}</span>
          </li>
        {/each}
      </ul>
    {:else}
      <p class="empty">Noch keine Mitglieder sichtbar.</p>
    {/if}
  </article>
</section>

<style>
  .panel {
    max-width: 64rem;
    background: rgba(255, 250, 243, 0.92);
    border: 1px solid #f2e9e1;
    border-radius: 1.5rem;
    padding: clamp(1.25rem, 3vw, 2rem);
    box-shadow: 0 1.5rem 3rem rgba(87, 82, 121, 0.08);
  }

  .kicker {
    margin: 0 0 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #286983;
    font-size: 0.85rem;
  }

  .lead,
  .empty,
  .member-list span {
    color: #5f5a79;
  }

  .card {
    margin-top: 1.5rem;
    padding: 1rem;
    border-radius: 1.1rem;
    background: linear-gradient(160deg, #faf4ed 0%, #fef6eb 100%);
    border: 1px solid #f2e9e1;
  }

  .member-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: 0.75rem;
  }

  .member-list li {
    display: grid;
    gap: 0.15rem;
  }
</style>
