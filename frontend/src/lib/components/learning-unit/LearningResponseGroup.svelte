<script lang="ts">
  import LearningCriteriaDetails from "$lib/components/learning-unit/LearningCriteriaDetails.svelte";
  import MarkdownContent from "$lib/components/ui/MarkdownContent.svelte";
  import type { LearningSubmission } from "$lib/types/learning";

  let {
    submission,
    openPanel = null
  }: {
    submission: LearningSubmission;
    openPanel?: "feedback" | "evaluation" | "submission" | null;
  } = $props();

  function fileSummary(): string {
    const first = submission.files?.[0];
    if (!first) {
      return "Keine Datei hinterlegt.";
    }
    return `${first.mime} · ${Math.max(1, Math.round(first.size / 1024))} KB`;
  }

  function hasEvaluation(): boolean {
    return (submission.analysis_json?.criteria_results?.length ?? 0) > 0;
  }
</script>

<section class="learning-response-group" aria-label="Rückmeldung zu deiner Abgabe">
  {#if submission.feedback_md || hasEvaluation()}
    <details class="learning-response-panel" open={openPanel === "feedback" || openPanel === "evaluation"}>
      <summary>Rückmeldung</summary>
      <div class="learning-response-panel__body learning-feedback-response">
        {#if submission.feedback_md}
          <MarkdownContent class="learning-feedback-response__copy markdown-prose" source={submission.feedback_md} />
        {/if}
        {#if hasEvaluation()}
          <LearningCriteriaDetails
            criteria={submission.analysis_json?.criteria_results ?? []}
            open={openPanel === "evaluation"}
          />
        {/if}
      </div>
    </details>
  {/if}

  <details class="learning-response-panel" open={openPanel === "submission"}>
    <summary>Meine Abgabe</summary>
    <div class="learning-response-panel__body">
      {#if submission.text_body}
        <MarkdownContent class="markdown-prose" source={submission.text_body} />
      {:else}
        <p>{fileSummary()}</p>
      {/if}
    </div>
  </details>
</section>
