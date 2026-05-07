<script lang="ts">
  import { buildSubmissionArtifactView } from "$lib/utils/submission-artifacts";
  import type { LearningSubmission } from "$lib/types/learning";

  let {
    submission
  }: {
    submission: LearningSubmission;
  } = $props();

  const artifact = $derived(buildSubmissionArtifactView(submission));
</script>

{#if artifact}
  <section class={`learning-submission-artifact learning-submission-artifact--${artifact.kind}`}>
    {#if artifact.kind === "makecode"}
      <div class="learning-submission-artifact__header">
        <p class="learning-submission-artifact__eyebrow">Codeansicht</p>
        <p class="learning-submission-artifact__meta">{artifact.filename} · {artifact.fileSummary}</p>
      </div>
      <pre class="learning-submission-artifact__code"><code>{artifact.code}</code></pre>
    {:else}
      <div class="learning-submission-artifact__header">
        <p class="learning-submission-artifact__eyebrow">Strukturansicht</p>
        <p class="learning-submission-artifact__meta">{artifact.fileSummary}</p>
      </div>
      <div class={`markdown-prose ${artifact.kind}-evidence`}>
        {@html artifact.html}
      </div>
    {/if}

    {#if artifact.downloadUrl}
      <a class="workspace-link-action" href={artifact.downloadUrl}>Originaldatei herunterladen</a>
    {/if}
  </section>
{/if}
