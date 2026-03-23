<script lang="ts">
  let { data } = $props();
</script>

<section class="hero">
  <p class="kicker">Milestone M0</p>
  <h2>SvelteKit trägt jetzt das Plattformfundament für GUSTAV.</h2>
  <p>
    Diese Seite ist die erste produktive App-Shell. Die Fachräume folgen in den
    nächsten Schritten über dedizierte Read-Models und objektorientierte
    Mutations-APIs.
  </p>

  <dl>
    <div>
      <dt>Startziel</dt>
      <dd>{data.bootstrap?.start_target ?? "offen"}</dd>
    </div>
    <div>
      <dt>Aktueller Nutzer</dt>
      <dd>{data.bootstrap?.user?.name ?? "nicht vorhanden"}</dd>
    </div>
    <div>
      <dt>Rolle</dt>
      <dd>{data.bootstrap?.user?.role ?? "guest"}</dd>
    </div>
  </dl>
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

  dl {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
    gap: 0.9rem;
    margin: 1.5rem 0 0;
  }

  dl div {
    border-radius: 1rem;
    background: #faf4ed;
    padding: 0.9rem 1rem;
  }

  dt {
    font-size: 0.9rem;
    color: #9893a5;
  }

  dd {
    margin: 0.35rem 0 0;
    font-weight: 600;
  }
</style>
