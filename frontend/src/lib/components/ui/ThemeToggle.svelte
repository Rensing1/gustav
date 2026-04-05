<script lang="ts">
  import type { ThemePreference } from "$lib/types/theme";

  let {
    currentTheme,
    onToggle
  }: {
    currentTheme: ThemePreference;
    onToggle: () => void;
  } = $props();

  const nextTheme = $derived(currentTheme === "dark" ? "light" : "dark");
  const buttonLabel = $derived(nextTheme === "dark" ? "Dark Mode aktivieren" : "Light Mode aktivieren");
</script>

<button
  class="theme-toggle"
  type="button"
  data-current-theme={currentTheme}
  aria-label={buttonLabel}
  title={buttonLabel}
  onclick={onToggle}
>
  {#if nextTheme === "dark"}
    <svg aria-hidden="true" viewBox="0 0 24 24" focusable="false">
      <path
        d="M14.5 3.5a8.5 8.5 0 1 0 6 14.5c-1 .3-2 .5-3 .5A8.5 8.5 0 0 1 9 10c0-2 .7-4 2-5.5 1-.8 2.2-1 3.5-1z"
        fill="none"
        stroke="currentColor"
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="1.8"
      />
    </svg>
  {:else}
    <svg aria-hidden="true" viewBox="0 0 24 24" focusable="false">
      <circle cx="12" cy="12" r="4.2" fill="none" stroke="currentColor" stroke-width="1.8" />
      <path
        d="M12 2.5v3M12 18.5v3M21.5 12h-3M5.5 12h-3M18.7 5.3l-2.1 2.1M7.4 16.6l-2.1 2.1M18.7 18.7l-2.1-2.1M7.4 7.4 5.3 5.3"
        fill="none"
        stroke="currentColor"
        stroke-linecap="round"
        stroke-width="1.8"
      />
    </svg>
  {/if}
</button>
