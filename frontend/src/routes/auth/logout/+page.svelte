<script lang="ts">
  import AuthFrame from "$lib/components/ui/AuthFrame.svelte";
</script>
<svelte:head><title>Abmelden | GUSTAV</title></svelte:head>
<AuthFrame embedded title="Von GUSTAV abmelden?" actionHref="/" actionLabel="Zurück">
  {#snippet children()}
    <p>Du kannst dich anschließend jederzeit wieder anmelden.</p>
    <form method="post" action="/auth/logout"><button class="button button--primary" type="submit">Abmelden</button></form>
  {/snippet}
</AuthFrame>
