<script lang="ts">
  import AuthFrame from "$lib/components/ui/AuthFrame.svelte";
</script>

<svelte:head>
  <title>Abgemeldet | GUSTAV</title>
</svelte:head>

<AuthFrame
  embedded
  title="Abgemeldet"
  actionHref="/auth/login"
  actionLabel="Erneut anmelden"
/>
