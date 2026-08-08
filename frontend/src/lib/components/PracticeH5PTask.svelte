<script lang="ts">
  import { onMount } from "svelte";
  import H5PTaskPlayer from "$lib/components/H5PTaskPlayer.svelte";

  let { sessionId, itemId, courseId, taskId, contentId, onCompleted } = $props<{
    sessionId: string;
    itemId: string;
    courseId: string;
    taskId: string;
    contentId: string;
    onCompleted: () => void | Promise<void>;
  }>();

  let context = $state<{
    practice_completion_token: string;
    context_id: string;
  } | null>(null);
  let error = $state("");

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
    onProgressPersisted={onCompleted}
  />
{:else}
  <p>Die H5P-Aufgabe wird vorbereitet.</p>
{/if}
