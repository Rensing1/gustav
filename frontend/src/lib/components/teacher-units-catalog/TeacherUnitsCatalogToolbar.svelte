<script lang="ts">
  let {
    query,
    sort,
    onQueryInput
  }: {
    query: string;
    sort: string;
    onQueryInput?: ((nextQuery: string) => void) | null;
  } = $props();
</script>

<section class="teacher-units-catalog-toolbar">
  <div class="teacher-units-catalog-toolbar__controls">
    <form class="teacher-units-catalog-toolbar__search" method="GET">
      <input type="hidden" name="sort" value={sort} />
      <label>
        <span>Suche</span>
        <input
          type="search"
          name="query"
          value={query}
          placeholder="Titel oder Thema..."
          aria-label="Suche"
          oninput={(event) => onQueryInput?.((event.currentTarget as HTMLInputElement).value)}
        />
      </label>
      <button class="workspace-link-action" type="submit">Suchen</button>
    </form>

    <form class="teacher-units-catalog-toolbar__sort" method="GET">
      <input type="hidden" name="query" value={query} />
      <label>
        <span>Sortierung</span>
        <select
          name="sort"
          aria-label="Sortierung"
          onchange={(event) => (event.currentTarget as HTMLSelectElement).form?.requestSubmit()}
        >
          <option value="updated_desc" selected={sort === "updated_desc"}>Zuletzt bearbeitet</option>
          <option value="title_asc" selected={sort === "title_asc"}>Titel A-Z</option>
        </select>
      </label>
    </form>
  </div>
</section>
