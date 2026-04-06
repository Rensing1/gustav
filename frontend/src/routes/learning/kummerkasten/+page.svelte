<script lang="ts">
  import ConcernBoxComposer from "$lib/components/concern-box/ConcernBoxComposer.svelte";
  import PageActionHead from "$lib/components/ui/PageActionHead.svelte";
  import type { ActionData, PageData } from "./$types";

  let { data, form }: { data: PageData; form?: ActionData } = $props();
</script>

<svelte:head>
  <title>Kummerkasten | GUSTAV</title>
</svelte:head>

<div class="workspace-page concern-box-page">
  <PageActionHead title={data.pageTitle} copy={data.pageCopy} />

  <ConcernBoxComposer
    courses={data.concernBox.courses}
    values={{
      courseId: form?.submit?.values?.courseId ?? "",
      messageText: form?.submit?.values?.messageText ?? "",
      anonymous: form?.submit?.values?.anonymous ?? true
    }}
    error={form?.submit?.error ?? null}
    sent={data.sent}
  />
</div>
