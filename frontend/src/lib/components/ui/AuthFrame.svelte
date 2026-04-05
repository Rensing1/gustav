<script lang="ts">
  let {
    eyebrow,
    title,
    body,
    actionHref,
    actionLabel,
    embedded = false
  }: {
    eyebrow: string;
    title: string;
    body: string;
    actionHref: string;
    actionLabel: string;
    embedded?: boolean;
  } = $props();
</script>

<section class:design-auth-shell--embedded={embedded} class="design-auth-shell">
  <article class="design-auth-frame">
    <p class="design-auth-frame__eyebrow">{eyebrow}</p>
    <h1 class="design-auth-frame__title">{title}</h1>
    <p class="design-auth-frame__body">{body}</p>
    <div class="design-auth-frame__actions">
      <a class="design-auth-frame__action workspace-button" href={actionHref}>{actionLabel}</a>
    </div>
  </article>
</section>
