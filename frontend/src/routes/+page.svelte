<section class="hero">
  <p class="kicker">Milestone M0</p>
  <h2>SvelteKit übernimmt jetzt den Einstieg in GUSTAV.</h2>
  <p>
    Diese Seite dient nur noch als Fallback, falls der serverseitige Redirect
    auf den passenden Raum nicht greift.
  </p>
</section>

<style>
  .hero {
    max-width: 56rem;
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

  h2 {
    margin: 0;
    font-size: clamp(1.5rem, 3vw, 2.3rem);
    line-height: 1.15;
  }

  p {
    font-size: 1.02rem;
    line-height: 1.7;
  }

</style>
