<script lang="ts">
  import { onMount } from "svelte";

  type WorkspaceOutlineGroup = {
    id: string;
    title: string | null;
    status?: string;
    items: Array<{ key: string; title: string; kind?: "material" | "task" }>;
  };

  let {
    title,
    groups,
    embedded = false,
    initialGroupId = null,
    onExpandGroup = undefined,
    activeItemKeys = [],
    onOpenItem,
    onRemoveGroup = undefined
  }: {
    title: string;
    embedded?: boolean;
    initialGroupId?: string | null;
    onExpandGroup?: (groupId: string) => void;
    groups: WorkspaceOutlineGroup[];
    activeItemKeys?: string[];
    onOpenItem: (itemKey: string) => void;
    onRemoveGroup?: ((groupId: string) => void) | undefined;
  } = $props();

  let compact = $state(true);
  let navigationOpen = $state(false);
  let expandedGroups = $state<string[]>([]);
  let previousGroupId: string | undefined;
  const currentGroup = $derived(groups.find((group) => group.items.some((item) => activeItemKeys.includes(item.key))) ?? groups.find((group) => group.id === initialGroupId) ?? groups[0]);

  // Follow the reader across modules without preventing manual disclosure changes.
  $effect(() => {
    const id = currentGroup?.id;
    if (id && id !== previousGroupId) {
      previousGroupId = id;
      expandedGroups = [id];
    }
  });

  onMount(() => {
    const query = window.matchMedia("(max-width: 64rem)");
    const update = () => {
      compact = !embedded && query.matches;
      navigationOpen = !compact;
    };
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  });

  function toggleGroup(id: string): void {
    if (!expandedGroups.includes(id)) onExpandGroup?.(id);
    expandedGroups = expandedGroups.includes(id)
      ? expandedGroups.filter((value) => value !== id)
      : [...expandedGroups, id];
  }

  function openItem(key: string): void {
    if (compact) navigationOpen = false;
    onOpenItem(key);
  }
</script>

<aside class:workspace-outline--embedded={embedded} class="workspace-outline workspace-outline--navigation" aria-label={title}>
  <details class="workspace-outline__disclosure" bind:open={navigationOpen}>
    <summary class="workspace-outline__header" tabindex={compact ? 0 : -1} onclick={(event) => { if (!compact) event.preventDefault(); }}>
      <div class="workspace-outline__copy">
        <h2>{embedded ? title : "Inhalt"}</h2>
        <span class="workspace-outline__current-module">{currentGroup?.title ?? title}</span>
      </div>
      <span class="workspace-outline__chevron" aria-hidden="true">⌄</span>
    </summary>
    <div class="workspace-outline__body">
      {#each groups as group (group.id)}
        <section class="workspace-outline__group">
          <div class="workspace-outline__group-head">
            <button
              class="workspace-outline__group-toggle"
              type="button"
              aria-expanded={expandedGroups.includes(group.id)}
              onclick={() => toggleGroup(group.id)}
            >
              <svg class="workspace-outline__group-chevron" viewBox="0 0 20 20" aria-hidden="true"><path d="m7 5 5 5-5 5" /></svg>
              <span>{group.title ?? title}</span>
            </button>
            {#if onRemoveGroup}
              <button aria-label={`Modul ${group.title} ausblenden`} class="workspace-outline__group-remove" type="button" onclick={() => onRemoveGroup(group.id)}>×</button>
            {/if}
          </div>
          {#if expandedGroups.includes(group.id)}
            <div class="workspace-outline__items">
              {#if group.status}<p class="workspace-outline__status" role="status">{group.status}</p>{/if}
              {#each group.items as item (item.key)}
                <button
                  class:workspace-outline__item--active={activeItemKeys.includes(item.key)}
                  class="workspace-outline__item"
                  type="button"
                  aria-current={activeItemKeys.includes(item.key) ? "location" : undefined}
                  onclick={() => openItem(item.key)}
                >
                  <svg class="workspace-outline__type-icon" viewBox="0 0 20 20" aria-hidden="true">
                    {#if item.kind === "task"}<path d="M3 14l-1 4 4-1L17 6l-3-3zM12 5l3 3" />
                    {:else}<path d="M5 2h7l4 4v12H5zM12 2v5h4M8 10h5M8 13h5" />{/if}
                  </svg>
                  <span class="workspace-outline__item-copy">
                    <span class="workspace-outline__item-label">{item.title}</span>
                    {#if item.kind !== "task" || !item.title.startsWith("Aufgabe")}<span class="workspace-outline__sr-only">{item.kind === "task" ? "Aufgabe" : "Material"}</span>{/if}
                  </span>
                </button>
              {/each}
            </div>
          {/if}
        </section>
      {/each}
    </div>
  </details>
</aside>
