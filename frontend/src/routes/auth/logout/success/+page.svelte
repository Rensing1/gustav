<svelte:head>
  <title>Abgemeldet | GUSTAV</title>
</svelte:head>

<section class="logout-card">
  <p class="eyebrow">Session beendet</p>
  <h2>Erfolgreich abgemeldet</h2>
  <p>
    Du wurdest von GUSTAV und dem Anmeldedienst abgemeldet. Die neue
    SvelteKit-Oberfläche hält diesen öffentlichen Rücksprung jetzt selbst.
  </p>
  <a class="button" href="/auth/login">Erneut anmelden</a>
</section>

<style>
  .logout-card {
    max-width: 38rem;
    background: rgba(255, 250, 243, 0.96);
    border: 1px solid #f2e9e1;
    border-radius: 1.5rem;
    padding: clamp(1.5rem, 3vw, 2.25rem);
    box-shadow: 0 1.5rem 3rem rgba(87, 82, 121, 0.08);
  }

  .eyebrow {
    margin: 0 0 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #286983;
    font-size: 0.85rem;
  }

  h2 {
    margin: 0;
    font-size: clamp(1.6rem, 3vw, 2.4rem);
    line-height: 1.15;
  }

  p {
    line-height: 1.7;
  }

  .button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    margin-top: 0.5rem;
    padding: 0.85rem 1.2rem;
    border-radius: 999px;
    background: #286983;
    color: #fffaf3;
    text-decoration: none;
    font-weight: 600;
  }

  .button:hover,
  .button:focus-visible {
    background: #1f566b;
    outline: none;
  }
</style>
