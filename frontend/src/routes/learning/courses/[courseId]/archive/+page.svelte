<script lang="ts">
  import PageActionHead from "$lib/components/ui/PageActionHead.svelte";
  import { renderMarkdown } from "$lib/utils/markdown";
  import type { ActionData, PageData } from "./$types";
  let { data, form }: { data: PageData; form?: ActionData } = $props();

  function taskTitle(snapshot: Record<string, unknown>): string {
    return String(snapshot.title || snapshot.instruction_md || "Aufgabe");
  }
</script>

<svelte:head><title>{data.portfolio.course.title} · Lernarchiv | GUSTAV</title></svelte:head>

<div class="workspace-page learning-portfolio">
  <PageActionHead backHref="/learning" backLabel="Zurück zum Lernraum" title={data.portfolio.course.title} copy="Deine persönliche Lernleistung aus diesem Kurs">
    {#snippet actions()}
      <form method="POST" action="?/export"><button class="workspace-link-action" type="submit">Lernleistung exportieren</button></form>
    {/snippet}
  </PageActionHead>

  {#if form?.exportJob}
    <p class="learning-portfolio__status" role="status">Der Export wird erstellt. Du kannst diese Seite später erneut öffnen.</p>
  {/if}
  {#if data.portfolio.latest_export?.status === "ready" && data.portfolio.latest_export.download_href}
    <p class="learning-portfolio__status"><a class="workspace-link-action" href={data.portfolio.latest_export.download_href}>Fertiges Lernarchiv herunterladen</a></p>
  {:else if data.portfolio.latest_export?.status === "pending" || data.portfolio.latest_export?.status === "generating"}
    <p class="learning-portfolio__status">Ein Export wird derzeit erstellt.</p>
  {:else if data.portfolio.latest_export?.status === "failed"}
    <p class="workspace-form-error">Der letzte Export konnte nicht erstellt werden ({data.portfolio.latest_export.error_code || "unbekannter Fehler"}).</p>
  {/if}
  {#if form?.exportError}<p class="workspace-form-error">{form.exportError}</p>{/if}

  <div class="learning-portfolio__list">
    {#each data.portfolio.submissions as submission}
      <article class="learning-portfolio__entry">
        <header><h2>{taskTitle(submission.task_snapshot)}</h2><time datetime={submission.completed_at || submission.created_at}>{new Date(submission.completed_at || submission.created_at).toLocaleDateString("de-DE")}</time></header>
        {#if submission.text_body}<div class="learning-portfolio__content"><h3>Meine Abgabe</h3><div class="markdown-prose">{@html renderMarkdown(submission.text_body)}</div></div>{/if}
        {#if submission.file_href}<a class="workspace-link-action" href={submission.file_href}>Originaldatei herunterladen</a>{/if}
        {#if submission.feedback_md}<div class="learning-portfolio__feedback"><h3>Rückmeldung</h3><div class="markdown-prose">{@html renderMarkdown(submission.feedback_md)}</div></div>{/if}
      </article>
    {:else}
      <p class="workspace-empty">Für diesen Kurs liegen keine finalen Lernleistungen vor.</p>
    {/each}
  </div>
</div>
