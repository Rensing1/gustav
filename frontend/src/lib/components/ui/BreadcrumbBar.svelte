<script lang="ts">
  export type BreadcrumbBarItem = {
    label: string;
    href?: string | null;
  };

  let {
    items,
    className = ""
  }: {
    items: BreadcrumbBarItem[];
    className?: string;
  } = $props();
</script>

<nav class={`breadcrumb-bar ${className}`.trim()} aria-label="Breadcrumb">
  {#each items as item, index}
    {#if index > 0}
      <span class="breadcrumb-bar__separator" aria-hidden="true">/</span>
    {/if}

    {#if item.href}
      <a href={item.href}>{item.label}</a>
    {:else}
      <span class="breadcrumb-bar__current" aria-current="page">{item.label}</span>
    {/if}
  {/each}
</nav>
