<script lang="ts">
  import { goto } from "$app/navigation";

  let {
    query,
    sort,
    onQueryInput
  }: {
    query: string;
    sort: string;
    onQueryInput?: ((nextQuery: string) => void) | null;
  } = $props();

  async function updateSort(nextSort: string): Promise<void> {
    const params = new URLSearchParams();
    params.set("sort", nextSort);
    if (query.trim()) {
      params.set("query", query.trim());
    }
    await goto(`/teaching/units?${params.toString()}`, {
      keepFocus: true,
      noScroll: true,
      replaceState: true,
    });
  }
</script>

<section class="teacher-units-catalog-toolbar teacher-catalog__toolbar">
  <div class="teacher-units-catalog-toolbar__controls teacher-catalog__toolbar-controls">
    <div class="teacher-units-catalog-toolbar__search">
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
    </div>

    <div class="teacher-units-catalog-toolbar__sort">
      <label>
        <span>Sortierung</span>
        <select
          name="sort"
          aria-label="Sortierung"
          onchange={(event) => void updateSort((event.currentTarget as HTMLSelectElement).value)}
        >
          <option value="updated_desc" selected={sort === "updated_desc"}>Zuletzt bearbeitet</option>
          <option value="title_asc" selected={sort === "title_asc"}>Titel A-Z</option>
        </select>
      </label>
    </div>
  </div>
</section>
