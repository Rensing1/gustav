<script lang="ts">
  import DialogMessage from "./DialogMessage.svelte";
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
      closing_prompt_md?: string | null;
    };
    closing_answer_md?: string | null;
    turns: TranscriptTurn[];
  };

  let { courseId, taskId, sessionId, compact = false, resultView = false }: { courseId: string; taskId: string; sessionId: string; compact?: boolean; resultView?: boolean } = $props();
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

{#snippet conversation()}
  {#if transcript}
    <div class="dialog-transcript dialog-transcript--document" role="log" aria-label="Früherer Dialogverlauf">
      <DialogMessage kind="ai" speaker={transcript.dialog.partner_name} markdown={transcript.dialog.opening_message_md} />
      {#each transcript.turns as turn (turn.id)}
        <DialogMessage kind="student" markdown={turn.student_message_md} usedStarter={Boolean(turn.used_sentence_starter_md)} />
        {#if turn.assistant_reply_md}
          <DialogMessage kind="ai" speaker={transcript.dialog.partner_name} markdown={turn.assistant_reply_md} />
        {/if}
      {/each}
    </div>
  {/if}
{/snippet}

{#snippet closingAnswer()}
  {#if transcript?.closing_answer_md}
    <section class="dialog-submission-answer" aria-label="Abschlussaufgabe und eigene Antwort">
      {#if transcript.dialog.closing_prompt_md}
        <h4>Zum Abschluss</h4>
        <div class="dialog-submission-answer__prompt markdown-prose">{@html renderMarkdown(transcript.dialog.closing_prompt_md)}</div>
      {/if}
      <div class="dialog-submission-answer__response">
        <h4>Deine Antwort</h4>
        <div class="markdown-prose">{@html renderMarkdown(transcript.closing_answer_md)}</div>
      </div>
    </section>
  {/if}
{/snippet}

{#if failed}
  <StatusMessage tone="error" title="Dialogverlauf nicht verfügbar" description="Der Dialogverlauf konnte nicht geladen werden." />
{:else if transcript}
  {#if compact && !(resultView && !transcript.closing_answer_md)}
    <div class="learning-submission-preview__details">
    <details class="learning-response-panel dialog-submission-history">
      <summary>Gespräch mit {transcript.dialog.partner_name}</summary>
      {@render conversation()}
    </details>
    </div>
    {@render closingAnswer()}
  {:else}
    {@render conversation()}
    {@render closingAnswer()}
  {/if}
{:else}
  <p class="workspace-note">Der Dialogverlauf wird geladen …</p>
{/if}
