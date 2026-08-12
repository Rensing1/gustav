<script lang="ts">
  import { renderMarkdown } from "$lib/utils/markdown";
  import { practiceClassificationLabel, practiceDueLabel } from "$lib/practice/practice-presentation";
  import type { LearningPracticeAttempt, LearningPracticeSessionItem } from "$lib/types/practice";

  let {
    attempt,
    sessionId,
    itemId,
    kind,
    solution,
    nowIso
  }: {
    attempt: LearningPracticeAttempt;
    sessionId: string;
    itemId: string;
    kind: LearningPracticeSessionItem["kind"];
    solution: string | null;
    nowIso: string;
  } = $props();

  const dueLabel = $derived(practiceDueLabel(attempt.due_at, nowIso));
</script>

<section class="practice-feedback" aria-live="polite" aria-labelledby="practice-feedback-title">
  <header class={`practice-feedback__heading practice-feedback__heading--${attempt.classification ?? "unknown"}`}>
    <span class="practice-feedback__icon" aria-hidden="true">
      <svg viewBox="0 0 24 24"><path d="m5 12 4 4L19 6" /></svg>
    </span>
    <div>
      <p class="practice-eyebrow">Deine Rückmeldung</p>
      <h3 id="practice-feedback-title">{practiceClassificationLabel(attempt.classification)}</h3>
    </div>
  </header>

  {#if attempt.feedback_md}
    <div class="practice-feedback__body markdown-prose">
      {@html renderMarkdown(attempt.feedback_md)}
    </div>
  {/if}

  {#if dueLabel}
    <p class="practice-feedback__due">
      <span aria-hidden="true">◷</span>
      {dueLabel}
    </p>
  {/if}

  {#if kind === "native"}
    {#if solution}
      <section class="practice-solution" aria-labelledby="practice-solution-title">
        <h4 id="practice-solution-title">Musterlösung</h4>
        <div class="markdown-prose">{@html renderMarkdown(solution)}</div>
      </section>
    {:else}
      <form method="POST" action="?/solution">
        <input type="hidden" name="session_id" value={sessionId} />
        <input type="hidden" name="item_id" value={itemId} />
        <button class="practice-button practice-button--secondary" type="submit">Musterlösung ansehen</button>
      </form>
    {/if}
  {/if}

  <form method="POST" action="?/continue" class="practice-feedback__continue">
    <input type="hidden" name="session_id" value={sessionId} />
    <button class="practice-button practice-button--primary practice-button--block" type="submit">
      Nächste Aufgabe <span aria-hidden="true">→</span>
    </button>
  </form>
</section>
