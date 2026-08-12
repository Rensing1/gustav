<script lang="ts">
  import { browser } from "$app/environment";
  import { invalidateAll } from "$app/navigation";
  import PracticeSessionSummary from "$lib/components/practice/PracticeSessionSummary.svelte";
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
  const summary = $derived(data.session.summary!);
  const endReason = $derived(data.session.end_reason!);

  $effect(() => {
    if (!browser || summary.pending_items === 0) return;
    const timer = window.setTimeout(() => void invalidateAll(), 1500);
    return () => window.clearTimeout(timer);
  });
</script>

<svelte:head><title>Übung abgeschlossen | GUSTAV</title></svelte:head>

<div class="workspace-page practice-page">
  <PracticeSessionSummary
    {endReason}
    {summary}
    nowIso={data.nowIso}
  />
</div>
