<script lang="ts">
  export type BreadcrumbBarItem = {
    label: string;
    href?: string | null;
  };

  let {
    items,
    className = "",
    reload = false
  }: {
    items: BreadcrumbBarItem[];
    className?: string;
    reload?: boolean;
  } = $props();
</script>

<nav class={`breadcrumb-bar ${className}`.trim()} aria-label="Breadcrumb">
  {#each items as item, index}
    {#if index > 0}
      <span class="breadcrumb-bar__separator" aria-hidden="true">/</span>
    {/if}

    {#if item.href}
      <a href={item.href} data-sveltekit-reload={reload || undefined}>{item.label}</a>
    {:else}
      <span class="breadcrumb-bar__current" aria-current="page">{item.label}</span>
    {/if}
  {/each}
</nav>
