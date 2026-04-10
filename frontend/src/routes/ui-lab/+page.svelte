<script lang="ts">
  import UiPreviewSurface from "$lib/components/ui/UiPreviewSurface.svelte";
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>UI Preview | GUSTAV</title>
</svelte:head>

<UiPreviewSurface userName={data.bootstrap.user.name} />
