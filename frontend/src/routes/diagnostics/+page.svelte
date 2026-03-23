<svelte:head>
  <title>Diagnostik | GUSTAV</title>
</svelte:head>

<section class="panel">
  <p class="kicker">Diagnostik</p>
  <h2>Kursbezogene Diagnostik startet jetzt als eigener Raum.</h2>
  <p class="lead">
    Der erste Schnitt fuehrt ueber die Kurskontexte. Oeffne einen Kurs im
    Teaching-Bereich und springe dort in die Matrix.
  </p>
</section>

<style>
  .panel {
    max-width: 52rem;
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

  .lead {
    margin: 0;
    color: #5f5a79;
  }
</style>
