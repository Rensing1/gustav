<script lang="ts">
  import { renderMarkdown } from "$lib/utils/markdown";
  import type { LearningSubmission } from "$lib/types/learning";

  let {
    submission
  }: {
    submission: LearningSubmission;
  } = $props();

  function fileSummary(): string {
    const first = submission.files?.[0];
    if (!first) {
      return "Keine Datei hinterlegt.";
    }
    return `${first.mime} · ${Math.max(1, Math.round(first.size / 1024))} KB`;
  }

  function evaluationSummary(): string {
    const score = submission.analysis_json?.score;
    if (typeof score === "number") {
      return `Punktestand: ${score}`;
    }
    if (submission.score_raw !== null && submission.score_raw !== undefined) {
      return `${submission.score_raw}/${submission.score_max ?? 0}`;
    }
    return submission.analysis_status;
  }
</script>

<section class="learning-response-group" aria-label="Abgabe und Auswertung">
  <details class="learning-response-panel">
    <summary>Abgabe</summary>
    <div class="learning-response-panel__body">
      {#if submission.text_body}
        <div class="markdown-prose">
          <p>{submission.text_body}</p>
        </div>
      {:else}
        <p>{fileSummary()}</p>
      {/if}
    </div>
  </details>

  <details class="learning-response-panel">
    <summary>Rückmeldung</summary>
    <div class="learning-response-panel__body">
      {#if submission.feedback_md}
        <div class="markdown-prose">
          {@html renderMarkdown(submission.feedback_md)}
        </div>
      {:else}
        <p>Es liegt noch keine Rückmeldung vor.</p>
      {/if}
    </div>
  </details>

  <details class="learning-response-panel">
    <summary>Bewertung</summary>
    <div class="learning-response-panel__body">
      <p>{evaluationSummary()}</p>
    </div>
  </details>
</section>
