<script lang="ts">
  import type { Snippet } from "svelte";

  type AuthAction = {
    href: string;
    label: string;
    variant?: "primary" | "secondary";
  };

  let {
    eyebrow,
    title,
    body,
    actionHref,
    actionLabel,
    actions = [],
    embedded = false,
    children
  }: {
    eyebrow: string;
    title: string;
    body: string;
    actionHref: string;
    actionLabel: string;
    actions?: AuthAction[];
    embedded?: boolean;
    children?: Snippet;
  } = $props();
</script>

<section class:design-auth-shell--embedded={embedded} class="design-auth-shell">
  <article class="design-auth-frame">
    <p class="design-auth-frame__eyebrow">{eyebrow}</p>
    <h1 class="design-auth-frame__title">{title}</h1>
    <p class="design-auth-frame__body">{body}</p>
    {#if children}
      <div class="design-auth-frame__content">
        {@render children()}
      </div>
    {/if}
    <div class="design-auth-frame__actions">
      {#each (actions.length
        ? actions
        : [{ href: actionHref, label: actionLabel, variant: "primary" satisfies "primary" }]) as action}
        <a
          class:workspace-button--ghost={action.variant === "secondary"}
          class="design-auth-frame__action workspace-button"
          href={action.href}
        >
          {action.label}
        </a>
      {/each}
    </div>
  </article>
</section>
