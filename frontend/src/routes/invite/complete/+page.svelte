<script lang="ts">
  import AuthFrame from "$lib/components/ui/AuthFrame.svelte";
  import type { ActionData } from "./$types";
  let { form }: { form: ActionData } = $props();
</script>
<svelte:head><title>Kurs beitreten | GUSTAV</title></svelte:head>
<AuthFrame embedded actionHref="/" actionLabel="Zur Startseite" title="Kurs beitreten" body="Deine Anmeldung ist abgeschlossen. Bestätige jetzt den Beitritt zu deinem Kurs.">
  {#if form?.message}<p role="alert">{form.message}</p>{/if}
  {#if form?.loginRequired}
    <a href="/auth/login?redirect=%2Finvite%2Fcomplete">Erneut anmelden</a>
  {:else}
    <form method="POST"><button class="workspace-button" type="submit">Kurs beitreten</button></form>
  {/if}
</AuthFrame>
