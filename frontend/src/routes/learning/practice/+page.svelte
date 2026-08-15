<script lang="ts">
  import { browser } from "$app/environment";
  import { invalidateAll } from "$app/navigation";
  import PracticeSessionWorkspace from "$lib/components/practice/PracticeSessionWorkspace.svelte";
  import PracticeStackSelector from "$lib/components/practice/PracticeStackSelector.svelte";
  import StatusMessage from "$lib/components/ui/StatusMessage.svelte";
  import { practiceSessionNeedsPolling } from "$lib/practice/practice-presentation";
  import type { PageData } from "./$types";

  let { data, form }: {
    data: PageData;
    form: { practice?: { error?: string; solution?: string } } | null;
  } = $props();

  $effect(() => {
    const itemStatus = data.activeSession?.current_item?.status ?? null;
    const attemptStatus = data.attempt?.status ?? null;
    if (!browser || !practiceSessionNeedsPolling(itemStatus, attemptStatus)) return;
    const timer = window.setTimeout(() => void invalidateAll(), 1500);
    return () => window.clearTimeout(timer);
  });
</script>

<svelte:head><title>Üben | GUSTAV</title></svelte:head>

<div class="workspace-page practice-page">
  {#if data.activeSession}
    <PracticeSessionWorkspace
      session={data.activeSession}
      attempt={data.attempt}
      attemptKey={data.attemptKey}
      solution={form?.practice?.solution ?? null}
      nowIso={data.nowIso}
    />
  {:else if data.stacks.length}
    <PracticeStackSelector
      stacks={data.stacks}
      selectedStack={data.selectedStack}
      selectedMode={data.selectedMode}
    />
  {:else}
    <section class="practice-summary">
      <header class="practice-summary__hero" data-tone="neutral">
        <span class="practice-summary__icon" aria-hidden="true">◷</span>
        <p class="practice-eyebrow">Deine Wiederholungen</p>
        <h2>Aktuell ist keine Übung verfügbar</h2>
        <p>Sobald ein Übungsmodul freigeschaltet ist, erscheint es hier.</p>
      </header>
      <div class="practice-summary__actions">
        <a class="practice-button practice-button--primary" href="/learning">Zum Lernraum</a>
      </div>
    </section>
  {/if}

  {#if form?.practice?.error}
    <StatusMessage
      tone="error"
      title="Die Aktion konnte nicht ausgeführt werden"
      description={form.practice.error}
      autoDismissMs={null}
    />
  {/if}
</div>
