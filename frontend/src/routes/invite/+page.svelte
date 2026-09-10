<script lang="ts">
  import { onMount } from "svelte";

  type Preview = { course_title: string; expires_at: string };
  let preview = $state<Preview | null>(null);
  let status = $state<"loading" | "ready" | "invalid">("loading");
  let accepting = $state(false);

  async function accept(mode: "register" | "login"): Promise<void> {
    accepting = true;
    const response = await fetch("/invite/accept", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ mode })
    }).catch(() => null);
    if (!response?.ok) {
      status = "invalid";
      accepting = false;
      return;
    }
    const result = await response.json() as { redirect: string };
    window.location.assign(result.redirect);
  }

  onMount(async () => {
    const token = window.location.hash.slice(1);
    // Remove the capability from browser history before any further navigation.
    history.replaceState(history.state, "", `${location.pathname}${location.search}`);
    if (!token) {
      status = "invalid";
      return;
    }
    const response = await fetch("/invite/intent", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ token })
    }).catch(() => null);
    if (!response?.ok) {
      status = "invalid";
      return;
    }
    preview = await response.json() as Preview;
    status = "ready";
  });
</script>

<svelte:head>
  <title>Kurseinladung | GUSTAV</title>
  <meta name="referrer" content="no-referrer" />
</svelte:head>

<div class="invite-page">
  <section class="invite-card design-auth-frame" aria-live="polite">
    <p class="design-auth-frame__eyebrow">GUSTAV-Kurseinladung</p>
    {#if status === "loading"}
      <h1>Einladung wird geprüft …</h1>
      <p>Bitte warte einen Moment.</p>
    {:else if status === "invalid"}
      <h1>Diese Einladung ist nicht mehr gültig</h1>
      <p>Bitte wende dich an deine Lehrkraft und bitte um einen neuen Klassenlink.</p>
    {:else if preview}
      <h1>{preview.course_title}</h1>
      <p>Mit dieser Einladung kannst du dem Kurs direkt beitreten.</p>
      <p class="invite-expiry">
        Gültig bis {new Intl.DateTimeFormat("de-DE", { dateStyle: "long", timeStyle: "short" }).format(new Date(preview.expires_at))}
      </p>
      <div class="invite-actions">
        <button class="workspace-link-action workspace-link-action--primary" type="button" disabled={accepting} onclick={() => void accept("register")}>
          Registrieren und beitreten
        </button>
        <button class="workspace-link-action" type="button" disabled={accepting} onclick={() => void accept("login")}>
          Anmelden und beitreten
        </button>
      </div>
      <p class="invite-privacy">Es werden keine Mitglieder-, Lehrkraft- oder E-Mail-Daten angezeigt.</p>
    {/if}
  </section>
</div>

<style>
  .invite-page { align-items: center; display: flex; justify-content: center; min-height: 70vh; padding: 2rem 1rem; }
  .invite-card { display: grid; gap: var(--space-4); color: var(--color-text); overflow-wrap: anywhere; }
  .invite-card h1, .invite-card p { margin: 0; }
  .invite-expiry { font-weight: 700; }
  .invite-actions { display: flex; flex-wrap: wrap; gap: 0.75rem; }
  .invite-privacy { color: var(--color-text-muted); font-size: 0.9rem; }
</style>
