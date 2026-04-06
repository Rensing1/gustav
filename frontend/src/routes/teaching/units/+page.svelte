<script lang="ts">
  import { goto } from "$app/navigation";
  import TeacherUnitsCatalogList from "$lib/components/teacher-units-catalog/TeacherUnitsCatalogList.svelte";
  import TeacherUnitsCatalogToolbar from "$lib/components/teacher-units-catalog/TeacherUnitsCatalogToolbar.svelte";
  import PageActionHead from "$lib/components/ui/PageActionHead.svelte";
  import type { ActionData, PageData } from "./$types";

  let { data, form }: { data: PageData; form?: ActionData } = $props();

  let createDialogOpen = $state(false);
  let queryDraft = $state("");
  let searchTimer: ReturnType<typeof setTimeout> | null = null;

  function scheduleLiveSearch(nextQuery: string): void {
    queryDraft = nextQuery;

    if (searchTimer) {
      clearTimeout(searchTimer);
    }

    searchTimer = setTimeout(async () => {
      const params = new URLSearchParams();
      params.set("sort", data.catalog.sort);
      if (nextQuery.trim()) {
        params.set("query", nextQuery.trim());
      }
      await goto(`/teaching/units?${params.toString()}`, {
        keepFocus: true,
        noScroll: true,
        replaceState: true,
      });
    }, 220);
  }

  $effect(() => {
    createDialogOpen = Boolean(data.showCreateDialog) || Boolean(form?.createUnit);
  });

  $effect(() => {
    queryDraft = data.catalog.query;
  });
</script>

<svelte:head>
  <title>Lerneinheiten | GUSTAV</title>
</svelte:head>

<div class="workspace-page workspace-units-catalog">
  <PageActionHead title={data.pageTitle}>
    {#snippet actions()}
      <a class="workspace-link-action" href={data.catalog.create_href}>Neue Lerneinheit</a>
    {/snippet}
  </PageActionHead>

  <section class="workspace-section workspace-units-catalog__workspace">
    <TeacherUnitsCatalogToolbar
      query={queryDraft}
      sort={data.catalog.sort}
      onQueryInput={scheduleLiveSearch}
    />

    <TeacherUnitsCatalogList
      activeViewLabel={data.catalog.views.find((view) => view.active)?.label ?? "Ergebnisse"}
      resultCount={data.catalog.result_count}
      items={data.catalog.items}
    />
  </section>
</div>

{#if createDialogOpen}
  <div
    class="workspace-modal-backdrop"
    role="presentation"
    tabindex="-1"
    onclick={() => (createDialogOpen = false)}
    onkeydown={(event) => {
      if (event.key === "Escape") {
        createDialogOpen = false;
      }
    }}
  >
    <div
      class="workspace-modal-card"
      role="dialog"
      tabindex="-1"
      aria-modal="true"
      aria-labelledby="create-unit-title"
      onclick={(event) => event.stopPropagation()}
      onkeydown={(event) => event.stopPropagation()}
    >
      <div class="workspace-modal-header">
        <div>
          <p class="workspace-label">Lerneinheiten</p>
          <h2 id="create-unit-title">Neue Lerneinheit</h2>
        </div>
        <button class="workspace-icon-button" type="button" aria-label="Dialog schließen" onclick={() => (createDialogOpen = false)}>✕</button>
      </div>

      <form method="POST" class="workspace-form">
        <label class="workspace-field">
          <span>Titel</span>
          <input name="title" type="text" value={form?.createUnit?.values?.title ?? ""} />
        </label>

        <label class="workspace-field">
          <span>Zusammenfassung</span>
          <textarea name="summary" rows="4">{form?.createUnit?.values?.summary ?? ""}</textarea>
        </label>

        {#if form?.createUnit?.error}
          <p class="workspace-form-error">{form.createUnit.error}</p>
        {/if}

        <div class="workspace-form-actions">
          <button class="workspace-link-action" type="submit">Lerneinheit anlegen</button>
        </div>
      </form>
    </div>
  </div>
{/if}
