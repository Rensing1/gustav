<script lang="ts">
  import LiveStatusPreview from "$lib/components/ui/LiveStatusPreview.svelte";
  import UiPreviewSurface from "$lib/components/ui/UiPreviewSurface.svelte";
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>UI Preview | GUSTAV</title>
</svelte:head>

<LiveStatusPreview />

<UiPreviewSurface userName={data.bootstrap.user.name} />
