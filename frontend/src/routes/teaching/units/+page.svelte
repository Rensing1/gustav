<script lang="ts">
  import { goto } from "$app/navigation";
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
      params.set("view", data.catalog.active_view);
      params.set("status", data.catalog.active_filters.status);
      if (data.catalog.active_filters.course_id) {
        params.set("course_id", data.catalog.active_filters.course_id);
      }
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
  <section class="workspace-section workspace-units-header">
    <p class="workspace-label">Lerneinheiten</p>
  </section>

  <section class="workspace-panel workspace-section workspace-units-listing">
    <div class="workspace-units-toolbar">
      <nav class="workspace-units-views" aria-label="Katalogansichten">
        {#each data.catalog.views as view}
          <a
            href={`/teaching/units?view=${view.id}`}
            class:workspace-item-active={view.active}
          >
            <strong>{view.label}</strong>
          </a>
        {/each}
      </nav>

      <div class="workspace-units-controls">
        <form class="workspace-units-search" method="GET">
          <input type="hidden" name="view" value={data.catalog.active_view} />
          <input type="hidden" name="status" value={data.catalog.active_filters.status} />
          <input type="hidden" name="course_id" value={data.catalog.active_filters.course_id} />
          <div class="workspace-search-input">
            <input
              id="units-query"
              type="search"
              name="query"
              value={queryDraft}
              placeholder="Titel oder Thema durchsuchen"
              oninput={(event) => scheduleLiveSearch((event.currentTarget as HTMLInputElement).value)}
            />
            <button class="workspace-link-action" type="submit">Suchen</button>
          </div>
        </form>

        <form method="GET">
          <input type="hidden" name="view" value={data.catalog.active_view} />
          <input type="hidden" name="query" value={data.catalog.query} />
          <input type="hidden" name="status" value={data.catalog.active_filters.status} />
          <select
            name="sort"
            class="workspace-select-submit"
            onchange={(event) => (event.currentTarget as HTMLSelectElement).form?.requestSubmit()}
          >
            <option value="updated_desc" selected={data.catalog.sort === "updated_desc"}>Zuletzt bearbeitet</option>
            <option value="title_asc" selected={data.catalog.sort === "title_asc"}>Titel A–Z</option>
          </select>
        </form>
      </div>
    </div>

    <div class="workspace-section-header">
      <div class="workspace-section-heading">
        <p class="workspace-label">{data.catalog.views.find((view) => view.active)?.label ?? "Ergebnisse"}</p>
        <p class="workspace-note">{data.catalog.result_count} Einheiten</p>
      </div>
    </div>

    {#if data.catalog.items.length}
      <div class="workspace-list workspace-units-list">
        {#each data.catalog.items as unit}
          <a href={unit.href}>
            <strong>{unit.title}</strong>
            {#if unit.topic}
              <p class="workspace-note">{unit.topic}</p>
            {/if}
            <span class="workspace-action">{unit.meta}</span>
          </a>
        {/each}
      </div>
    {:else}
      <p class="workspace-empty">Noch keine passenden Lerneinheiten gefunden.</p>
    {/if}
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
