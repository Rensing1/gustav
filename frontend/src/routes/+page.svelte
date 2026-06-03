<script lang="ts">
  import AuthFrame from "$lib/components/ui/AuthFrame.svelte";

  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();

  function withRedirect(path: string): string {
    if (!data.redirectPath) {
      return path;
    }
    const params = new URLSearchParams({ redirect: data.redirectPath });
    return `${path}?${params.toString()}`;
  }

  const entryActions = [
    { href: withRedirect("/auth/login"), label: "Anmelden", variant: "primary" as const },
    { href: withRedirect("/register"), label: "Registrieren", variant: "secondary" as const },
    { href: withRedirect("/forgot-password"), label: "Passwort vergessen", variant: "secondary" as const },
  ];
</script>

<svelte:head>
  <title>Anmeldung | GUSTAV</title>
</svelte:head>

<AuthFrame
  embedded
  title="Anmelden"
  actionHref="/auth/login"
  actionLabel="Anmelden"
  actions={entryActions}
>
  {#snippet children()}
    {#if data.reason === "session-expired" || data.reason === "session_expired"}
      <p class="auth-note">Sitzung abgelaufen. Nach der Anmeldung geht es direkt zurück.</p>
    {:else if data.redirectPath}
      <p class="auth-note">Rücksprung: <code>{data.redirectPath}</code></p>
    {/if}
  {/snippet}
</AuthFrame>
