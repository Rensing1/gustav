<script lang="ts">
  import AuthFrame from "$lib/components/ui/AuthFrame.svelte";

  import type { ActionData, PageData } from "./$types";

  let { data, form }: { data: PageData; form: ActionData | null } = $props();
</script>

<svelte:head>
  <title>Registrieren | GUSTAV</title>
</svelte:head>

<AuthFrame
  eyebrow="Registrierung"
  title="Schulzugang vorbereiten"
  body="GUSTAV prüft die Schul-E-Mail vor dem Wechsel zum Anmeldedienst. Die eigentliche Registrierung und Verifizierung bleiben beim IdP."
  actionHref="/auth/register"
  actionLabel="Weiter zum Anmeldedienst"
  actions={[
    { href: "/", label: "Zurück", variant: "secondary" },
    { href: "/auth/login", label: "Direkt anmelden", variant: "secondary" },
  ]}
>
  {#snippet children()}
    <form class="auth-form" method="POST" action="/register">
      <input name="redirect" type="hidden" value={data.redirectPath ?? ""} />
      <label class="auth-field" for="login_hint">
        <span class="auth-field__label">Schul-E-Mail</span>
        <input
          id="login_hint"
          class="auth-input"
          name="login_hint"
          type="email"
          value={form?.loginHint ?? ""}
          autocomplete="email"
          required
        />
        <span class="auth-field__hint">Nur freigegebene Schul-Domains dürfen sich selbst registrieren.</span>
      </label>
      {#if form?.error === "invalid_email_domain"}
        <p class="auth-field__error">Diese E-Mail-Domain ist für die Selbstregistrierung nicht freigegeben.</p>
      {/if}
      <div class="auth-actions">
        <button class="workspace-button auth-submit" type="submit">Registrieren</button>
      </div>
    </form>
  {/snippet}
</AuthFrame>
