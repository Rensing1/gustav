<script lang="ts">
  import AuthFrame from "$lib/components/ui/AuthFrame.svelte";

  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>Passwort vergessen | GUSTAV</title>
</svelte:head>

<AuthFrame
  embedded
  title="Passwort zurücksetzen"
  actionHref="/auth/forgot"
  actionLabel="Zum Reset"
  actions={[
    { href: "/", label: "Zurück", variant: "secondary" },
    { href: "/auth/login", label: "Direkt anmelden", variant: "secondary" },
  ]}
>
  {#snippet children()}
    <form class="auth-form" method="POST" action="/forgot-password">
      <input name="redirect" type="hidden" value={data.redirectPath ?? ""} />
      <label class="auth-field" for="login_hint">
        <span class="auth-field__label">Schul-E-Mail</span>
        <input
          id="login_hint"
          class="auth-input"
          name="login_hint"
          type="email"
          autocomplete="email"
        />
        <span class="auth-field__hint">Optional.</span>
      </label>
      <div class="auth-actions">
        <button class="workspace-button auth-submit" type="submit">Passwort vergessen</button>
      </div>
    </form>
  {/snippet}
</AuthFrame>
