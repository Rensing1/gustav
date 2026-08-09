<script lang="ts">
  import { onMount } from "svelte";
  import { renderMarkdown } from "$lib/utils/markdown";
  import StatusMessage from "$lib/components/ui/StatusMessage.svelte";

  type TranscriptTurn = {
    id: string;
    student_message_md: string;
    used_sentence_starter_md?: string | null;
    assistant_reply_md?: string | null;
  };

  type Transcript = {
    dialog: {
      partner_name: string;
      opening_message_md: string;
    };
    closing_answer_md?: string | null;
    turns: TranscriptTurn[];
  };

  let { courseId, taskId, sessionId }: { courseId: string; taskId: string; sessionId: string } = $props();
  let transcript = $state<Transcript | null>(null);
  let failed = $state(false);

  onMount(() => {
    let current = true;
    const url = `/api/learning/courses/${encodeURIComponent(courseId)}/tasks/${encodeURIComponent(taskId)}/dialog-sessions/${encodeURIComponent(sessionId)}`;
    void fetch(url, { credentials: "include", cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("dialog_transcript_unavailable");
        const payload = (await response.json()) as Transcript | { session?: Transcript };
        if (current) transcript = "session" in payload && payload.session ? payload.session : payload as Transcript;
      })
      .catch(() => {
        if (current) failed = true;
      });
    return () => {
      current = false;
    };
  });
</script>

{#if failed}
  <StatusMessage tone="error" title="Dialogverlauf nicht verfügbar" description="Der Dialogverlauf konnte nicht geladen werden." />
{:else if transcript}
  <div class="learner-reference-transcript" role="log" aria-label="Früherer Dialogverlauf">
    <article class="learner-reference-transcript__message learner-reference-transcript__message--ai">
      <p class="learner-reference-document__meta">KI · {transcript.dialog.partner_name}</p>
      <div class="learner-reference-document__prose markdown-prose">
        {@html renderMarkdown(transcript.dialog.opening_message_md)}
      </div>
    </article>
    {#each transcript.turns as turn (turn.id)}
      <article class="learner-reference-transcript__message learner-reference-transcript__message--student">
        <p class="learner-reference-document__meta">Schüler · Du</p>
        <div class="learner-reference-document__prose markdown-prose">
          {@html renderMarkdown(turn.student_message_md)}
        </div>
        {#if turn.used_sentence_starter_md}
          <small>Hilfestellung: Satzanfang verwendet</small>
        {/if}
      </article>
      {#if turn.assistant_reply_md}
        <article class="learner-reference-transcript__message learner-reference-transcript__message--ai">
          <p class="learner-reference-document__meta">KI · {transcript.dialog.partner_name}</p>
          <div class="learner-reference-document__prose markdown-prose">
            {@html renderMarkdown(turn.assistant_reply_md)}
          </div>
        </article>
      {/if}
    {/each}
    {#if transcript.closing_answer_md}
      <section class="learner-reference-transcript__closing">
        <p class="learner-reference-document__meta">Abschlussantwort</p>
        <div class="learner-reference-document__prose markdown-prose">
          {@html renderMarkdown(transcript.closing_answer_md)}
        </div>
      </section>
    {/if}
  </div>
{:else}
  <p class="workspace-note">Der Dialogverlauf wird geladen …</p>
{/if}
