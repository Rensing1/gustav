<script lang="ts">
  export type ModeSwitchOption = {
    label: string;
    href?: string;
    current: boolean;
    onSelect?: (() => void) | null;
  };

  let {
    label,
    options
  }: {
    label: string;
    options: ModeSwitchOption[];
  } = $props();
</script>

<nav class="mode-switch" aria-label={label}>
  {#each options as option}
    {#if option.href}
      <a class="mode-switch__option" data-current={option.current} href={option.href} aria-current={option.current ? "page" : undefined}>
        {option.label}
      </a>
    {:else}
      <button
        class="mode-switch__option"
        data-current={option.current}
        type="button"
        aria-pressed={option.current}
        onclick={() => option.onSelect?.()}
      >
        {option.label}
      </button>
    {/if}
  {/each}
</nav>
