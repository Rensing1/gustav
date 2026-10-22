<script lang="ts">
  import AuthFrame from "$lib/components/ui/AuthFrame.svelte";
  import type { PageData } from "./$types";
  let { data }: { data: PageData } = $props();
</script>

<svelte:head><title>{data.title} | GUSTAV</title></svelte:head>
<AuthFrame embedded title={data.title} body={data.message} actionHref={data.actionHref} actionLabel={data.actionLabel} />
