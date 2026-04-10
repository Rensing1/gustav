<script lang="ts">
  import ConcernBoxInboxEntry from "$lib/components/concern-box/ConcernBoxInboxEntry.svelte";
  import ModeSwitch from "$lib/components/ui/ModeSwitch.svelte";
  import PageActionHead from "$lib/components/ui/PageActionHead.svelte";
  import QuietList from "$lib/components/ui/QuietList.svelte";
  import type { ActionData, PageData } from "./$types";

  let { data, form }: { data: PageData; form?: ActionData } = $props();
</script>

<svelte:head>
  <title>Kummerkasten | GUSTAV</title>
</svelte:head>

<div class="workspace-page concern-box-page">
  <PageActionHead title={data.pageTitle} copy={data.pageCopy} />

  <section class="concern-box-inbox">
    <ModeSwitch
      label="Kummerkasten-Ansicht"
      options={data.concernBox.scopes.map((scope) => ({
        label: scope.label,
        href: `/teaching/kummerkasten?scope=${scope.id}`,
        current: scope.active
      }))}
    />

    {#if form?.archive?.error}
      <p class="workspace-form-error">{form.archive.error}</p>
    {/if}
    {#if form?.restore?.error}
      <p class="workspace-form-error">{form.restore.error}</p>
    {/if}

    {#if data.concernBox.entries.length}
      <QuietList>
        {#each data.concernBox.entries as entry}
          <ConcernBoxInboxEntry {entry} />
        {/each}
      </QuietList>
    {:else}
      <p class="workspace-empty">Keine Beiträge in dieser Ansicht.</p>
    {/if}
  </section>
</div>
