<script lang="ts">
  let {
    href,
    title,
    meta = null
  }: {
    href: string;
    title: string;
    meta?: string | null;
  } = $props();
</script>

<li>
  <a class="quiet-list-entry" href={href}>
    <strong>{title}</strong>
    {#if meta}
      <span class="quiet-list-entry__meta">{meta}</span>
    {/if}
  </a>
</li>
