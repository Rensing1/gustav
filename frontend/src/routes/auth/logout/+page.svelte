<script lang="ts">
  import AuthFrame from "$lib/components/ui/AuthFrame.svelte";
</script>
<svelte:head><title>Abmelden | GUSTAV</title></svelte:head>
<AuthFrame embedded title="Von GUSTAV abmelden?" actionHref="/" actionLabel="Abbrechen" actions={[{ href: "/", label: "Abbrechen", variant: "secondary" }]}>
  {#snippet children()}
    <p>Du kannst dich anschließend jederzeit wieder anmelden.</p>
  {/snippet}
  {#snippet actionContent()}
    <form method="post" action="/auth/logout"><button class="auth-submit" type="submit">Abmelden</button></form>
  {/snippet}
</AuthFrame>
