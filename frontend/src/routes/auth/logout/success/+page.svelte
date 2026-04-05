<script lang="ts">
  import AuthFrame from "$lib/components/ui/AuthFrame.svelte";
</script>

<svelte:head>
  <title>Abgemeldet | GUSTAV</title>
</svelte:head>

<AuthFrame
  eyebrow="Session beendet"
  title="Erfolgreich abgemeldet"
  body="Du wurdest von GUSTAV und dem Anmeldedienst abgemeldet. Der Rücksprung bleibt bewusst Teil derselben Produktsprache."
  actionHref="/auth/login"
  actionLabel="Erneut anmelden"
/>
