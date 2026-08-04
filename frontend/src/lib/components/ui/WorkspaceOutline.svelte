<script lang="ts">
  type WorkspaceOutlineGroup = {
    id: string;
    title: string | null;
    items: Array<{ key: string; title: string }>;
  };

  let {
    title,
    groups,
    activeItemKeys = [],
    onOpenItem,
    onRemoveGroup = undefined
  }: {
    title: string;
    groups: WorkspaceOutlineGroup[];
    activeItemKeys?: string[];
    onOpenItem: (itemKey: string) => void;
    onRemoveGroup?: ((groupId: string) => void) | undefined;
  } = $props();

  function isActive(itemKey: string): boolean {
    return activeItemKeys.includes(itemKey);
  }
</script>

<aside class="workspace-outline" aria-label={title}>
  <details class="workspace-outline__disclosure" open>
  <summary class="workspace-outline__header">
    <div class="workspace-outline__copy">
      <h2>{title}</h2>
    </div>
    <span class="workspace-outline__chevron" aria-hidden="true">⌄</span>
  </summary>

  <div class="workspace-outline__body">
    {#each groups as group}
      <section class="workspace-outline__group">
        {#if group.title}
          <div class="workspace-outline__group-head">
            <p class="workspace-outline__group-title">{group.title}</p>
            {#if onRemoveGroup}
              <button
                aria-label={`Modul ${group.title} ausblenden`}
                class="workspace-outline__group-remove"
                title={`Modul ${group.title} ausblenden`}
                type="button"
                onclick={() => onRemoveGroup(group.id)}
              >
                ×
              </button>
            {/if}
          </div>
        {/if}

        <div class="workspace-outline__items">
          {#each group.items as item}
            <button
              class:workspace-outline__item--active={isActive(item.key)}
              class="workspace-outline__item"
              type="button"
              onclick={() => onOpenItem(item.key)}
            >
              <span class="workspace-outline__item-copy">
                <span class="workspace-outline__item-label">{item.title}</span>
              </span>
            </button>
          {/each}
        </div>
      </section>
    {/each}
  </div>
  </details>
</aside>
