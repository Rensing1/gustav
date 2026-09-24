<script lang="ts">
  import { onMount } from "svelte";
  import H5PTaskPlayer from "$lib/components/H5PTaskPlayer.svelte";
  import type { H5PPersistedResult } from "$lib/types/h5p";
  import type { LearningPracticeAttempt } from "$lib/types/practice";

  let { sessionId, itemId, courseId, taskId, contentId, onCompleted } = $props<{
    sessionId: string;
    itemId: string;
    courseId: string;
    taskId: string;
    contentId: string;
    onCompleted: (attempt: LearningPracticeAttempt | null) => void | Promise<void>;
  }>();

  let context = $state<{
    practice_completion_token: string;
    context_id: string;
  } | null>(null);
  let error = $state("");

  async function handlePersisted(result: H5PPersistedResult): Promise<void> {
    if (result.kind !== "practice") {
      return;
    }
    try {
      const response = await fetch(
        `/api/learning/practice/attempts/${encodeURIComponent(result.attemptId)}`,
        { credentials: "include" }
      );
      if (!response.ok) {
        await onCompleted(null);
        return;
      }
      await onCompleted(await response.json() as LearningPracticeAttempt);
    } catch {
      // The score is already durable; missing detail must not trap the learner.
      await onCompleted(null);
    }
  }

  onMount(async () => {
    const response = await fetch(
      `/api/learning/practice/sessions/${encodeURIComponent(sessionId)}/items/${encodeURIComponent(itemId)}/h5p-context`,
      { method: "POST", credentials: "include" }
    );
    if (!response.ok) {
      const payload = await response.json().catch(() => ({})) as { detail?: string };
      error = payload.detail || "H5P-Präsentation konnte nicht gestartet werden.";
      return;
    }
    context = await response.json();
  });
</script>

{#if error}
  <p role="alert">{error}</p>
{:else if context}
  <H5PTaskPlayer
    {courseId}
    {taskId}
    {contentId}
    practiceContext={{
      sessionId,
      itemId,
      completionToken: context.practice_completion_token,
      contextId: context.context_id
    }}
    onProgressPersisted={handlePersisted}
  />
{:else}
  <p>Die H5P-Aufgabe wird vorbereitet.</p>
{/if}
