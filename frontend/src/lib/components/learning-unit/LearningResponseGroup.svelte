<script lang="ts">
  import LearningCriteriaDetails from "$lib/components/learning-unit/LearningCriteriaDetails.svelte";
  import { renderMarkdown } from "$lib/utils/markdown";
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
          <div class="learning-feedback-response__copy markdown-prose">
            {@html renderMarkdown(submission.feedback_md)}
          </div>
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
        <div class="markdown-prose">
          {@html renderMarkdown(submission.text_body)}
        </div>
      {:else}
        <p>{fileSummary()}</p>
      {/if}
    </div>
  </details>
</section>
