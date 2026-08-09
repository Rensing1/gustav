<script lang="ts">
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
  {#if submission.feedback_md}
    <details class="learning-response-panel" open={openPanel === "feedback"}>
      <summary>Rückmeldung</summary>
      <div class="learning-response-panel__body markdown-prose">
        {@html renderMarkdown(submission.feedback_md)}
      </div>
    </details>
  {/if}

  {#if hasEvaluation()}
    <details class="learning-response-panel" open={openPanel === "evaluation"}>
      <summary>Auswertung</summary>
      <div class="learning-response-panel__body">
        <ul class="learning-unit-criteria">
          {#each submission.analysis_json?.criteria_results ?? [] as criterion}
            <li>
              <strong>{criterion.criterion}</strong>
              {#if criterion.score !== undefined && criterion.score !== null}
                : {criterion.score}/{criterion.max_score ?? 10}
              {/if}
              {#if criterion.explanation_md}
                <div class="markdown-prose">
                  {@html renderMarkdown(criterion.explanation_md)}
                </div>
              {/if}
            </li>
          {/each}
        </ul>
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
