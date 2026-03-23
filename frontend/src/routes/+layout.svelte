<script lang="ts">
  let { data, children } = $props();

  const bootstrap = data.bootstrap;
  const user = bootstrap?.user ?? null;
</script>

<svelte:head>
  <title>GUSTAV</title>
</svelte:head>

<div class="app-shell">
  <aside class="rail">
    <div class="brand">
      <span class="brand-mark">G</span>
      <div>
        <strong>GUSTAV</strong>
        <p>Browser-BFF</p>
      </div>
    </div>

    <nav aria-label="Hauptnavigation">
      <a href="/">Start</a>
      <a href="/learning">Lernraum</a>
      <a href="/teaching">Lehrenden-Welt</a>
      <a href="/diagnostics">Diagnostik</a>
      <a href="/live">Live</a>
    </nav>
  </aside>

  <main class="content">
    <header class="topbar">
      <div>
        <p class="eyebrow">Neue Web-Plattform</p>
        <h1>{bootstrap?.start_target ?? "session-bootstrap"}</h1>
      </div>

      <div class="user-card">
        <span>{user?.name ?? "Nicht angemeldet"}</span>
        <small>{user?.role ?? "guest"}</small>
      </div>
    </header>

    {@render children()}
  </main>
</div>

<style>
  :global(body) {
    margin: 0;
    font-family: "Lexend", "Segoe UI", sans-serif;
    background:
      radial-gradient(circle at top left, rgba(40, 105, 131, 0.12), transparent 28rem),
      linear-gradient(180deg, #faf4ed 0%, #fffaf3 100%);
    color: #575279;
  }

  .app-shell {
    min-height: 100vh;
    display: grid;
    grid-template-columns: minmax(15rem, 18rem) 1fr;
  }

  .rail {
    border-right: 1px solid #f2e9e1;
    background: rgba(255, 250, 243, 0.88);
    backdrop-filter: blur(1rem);
    padding: 1.5rem;
  }

  .brand {
    display: flex;
    gap: 0.9rem;
    align-items: center;
    margin-bottom: 2rem;
  }

  .brand p,
  .eyebrow,
  .user-card small {
    margin: 0;
    color: #9893a5;
  }

  .brand-mark {
    width: 2.75rem;
    height: 2.75rem;
    border-radius: 0.9rem;
    display: grid;
    place-items: center;
    background: #286983;
    color: #fffaf3;
    font-weight: 700;
  }

  nav {
    display: grid;
    gap: 0.5rem;
  }

  nav a {
    color: inherit;
    text-decoration: none;
    border-radius: 0.9rem;
    padding: 0.75rem 0.9rem;
  }

  nav a:hover,
  nav a:focus-visible {
    background: rgba(40, 105, 131, 0.08);
    outline: none;
  }

  .content {
    padding: 1.5rem;
  }

  .topbar {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: start;
    margin-bottom: 1.5rem;
  }

  .topbar h1 {
    margin: 0.25rem 0 0;
    font-size: clamp(1.9rem, 3vw, 2.8rem);
    line-height: 1.1;
  }

  .user-card {
    background: rgba(255, 250, 243, 0.92);
    border: 1px solid #f2e9e1;
    border-radius: 1rem;
    padding: 0.85rem 1rem;
    display: grid;
    gap: 0.15rem;
  }

  @media (max-width: 900px) {
    .app-shell {
      grid-template-columns: 1fr;
    }

    .rail {
      border-right: 0;
      border-bottom: 1px solid #f2e9e1;
    }

    nav {
      grid-template-columns: repeat(auto-fit, minmax(8rem, 1fr));
    }

    .topbar {
      flex-direction: column;
    }
  }
</style>

