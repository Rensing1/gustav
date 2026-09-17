<script lang="ts">
  import { untrack } from "svelte";
  import StatusMessage from "$lib/components/ui/StatusMessage.svelte";
  import LearningCriteriaDetails from "./LearningCriteriaDetails.svelte";
  import LearningSubmissionArtifactView from "./LearningSubmissionArtifactView.svelte";
  import LearningDialogTranscriptDocument from "./LearningDialogTranscriptDocument.svelte";
  import { renderMarkdown } from "$lib/utils/markdown";
  import { buildSubmissionArtifactView } from "$lib/utils/submission-artifacts";
  import { submissionPreviewText, type SubmissionPreviewState } from "$lib/learning-unit/submission-preview";

  let { courseId, taskId, taskTitle, hasSubmission, state: previewState, active = true, newerDraft = false,
    onLoad = null, onContinueDraft = null }: {
    courseId: string; taskId: string; taskTitle: string; hasSubmission: boolean;
    state?: SubmissionPreviewState; active?: boolean; newerDraft?: boolean;
    onLoad?: (() => void | Promise<void>) | null;
    onContinueDraft?: (() => void) | null;
  } = $props();

  let root = $state<HTMLDivElement | null>(null);
  let expanded = $state(false);
  let clipped = $state(false);
  let imageFailed = $state(false);
  let previousId = $state<string | null>(null);
  const submission = $derived(previewState?.submission ?? null);
  const file = $derived(submission?.files?.[0] ?? null);
  const isImage = $derived(file?.mime.startsWith("image/") ?? false);
  const isPdf = $derived(file?.mime === "application/pdf");
  const artifact = $derived(submission ? buildSubmissionArtifactView(submission) : null);
  const plainText = $derived(submissionPreviewText(submission?.text_body));
  const processing = $derived(submission?.analysis_status === "pending" || submission?.analysis_status === "extracted");
  const failed = $derived(submission?.analysis_status === "failed");
  const canExpand = $derived(clipped || Boolean(file || submission?.dialog_session_id || submission?.feedback_md
    || submission?.analysis_json?.criteria_results?.length || processing || failed));
  const bodyId = $derived(`submission-preview-${taskId}`);

  $effect(() => {
    if (submission?.id !== previousId) {
      previousId = submission?.id ?? null;
      expanded = false;
      clipped = false;
      imageFailed = false;
    }
  });

  $effect(() => {
    if (!root || !active || !hasSubmission) return;
    if (typeof IntersectionObserver === "undefined") {
      untrack(() => { void onLoad?.(); });
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        observer.disconnect();
        void onLoad?.();
      }
    });
    // Start when the task row is visible, even if its answer begins just below
    // the viewport (common after returning from the editor on a tablet).
    observer.observe(root.closest(".learner-task-reading") ?? root);
    return () => observer.disconnect();
  });

  function measurePreview(node: HTMLElement, _text: string) {
    const measure = () => { clipped = node.scrollHeight > node.clientHeight && node.clientHeight > 0; };
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    observer?.observe(node);
    queueMicrotask(measure);
    return { update() { queueMicrotask(measure); }, destroy() { observer?.disconnect(); } };
  }

  function timestamp(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "" : new Intl.DateTimeFormat("de-DE", {
      day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin"
    }).format(date);
  }

  function fileDescription() {
    if (!file) return "Datei";
    const type = isImage ? "Bild" : isPdf ? "PDF" : artifact?.kind === "makecode" ? "Calliope-Datei"
      : artifact?.kind === "scratch" ? "Scratch-Datei" : artifact?.kind === "filius" ? "Filius-Datei" : "Datei";
    return `${type} · ${Math.max(1, Math.round(file.size / 1024))} KB`;
  }
</script>

<div bind:this={root} class="learning-submission-preview-anchor">
  {#if previewState?.status === "failed"}
    <StatusMessage tone="error" title="Abgabe konnte nicht geladen werden" actionLabel="Erneut versuchen" onAction={onLoad} />
  {:else if (previewState?.status === "loading" && !submission) || (hasSubmission && !previewState)}
    <p class="workspace-note" role="status">Abgabe wird geladen …</p>
  {:else if submission}
    <section class="learning-submission-preview" class:learning-submission-preview--expanded={expanded} aria-label={`Eigene Abgabe zu ${taskTitle}`}>
      <header class="learning-submission-preview__header">
        <strong>{submission.intent === "submit" ? "Meine Abgabe" : "Mein Entwurf"}</strong>
        <span class="learning-submission-preview__meta">
          <span>{submission.intent === "submit" ? "Abgegeben" : "Noch nicht abgegeben"}</span>
          <span aria-hidden="true">·</span>
          <time datetime={submission.created_at}>{timestamp(submission.created_at)}</time>
        </span>
      </header>
      <div class="learning-submission-preview__body" id={bodyId}>
        {#if expanded}
          {#if file}
            {#if isImage && !imageFailed}
              <img class="learning-submission-preview__image" src={file.url} alt={`Eigene Bildabgabe zu ${taskTitle}`} loading="lazy" onerror={() => { imageFailed = true; }} />
            {:else if isPdf}
              <iframe class="learning-submission-preview__pdf" src={file.url} title={`Abgabe zu ${taskTitle}`} loading="lazy"></iframe>
            {:else if artifact}
              <LearningSubmissionArtifactView {submission} />
            {/if}
            {#if imageFailed}<p class="workspace-note">Bild konnte nicht geladen werden.</p>{/if}
            {#if !artifact}
              <p class="learning-submission-preview__meta">{fileDescription()}</p>
            {/if}
            {#if !artifact?.downloadUrl}
              <a class="workspace-link-action" href={file.url} target="_blank" rel="noreferrer">Datei öffnen</a>
            {/if}
          {:else if submission.text_body}
            <div class="markdown-prose">{@html renderMarkdown(submission.text_body)}</div>
          {:else if submission.kind === "h5p"}
            <p>Interaktive Bearbeitung gespeichert.</p>
          {/if}
          {#if submission.kind === "dialog" && submission.dialog_session_id}
            <LearningDialogTranscriptDocument {courseId} {taskId} sessionId={submission.dialog_session_id} />
          {/if}
          {#if processing}
            <StatusMessage tone="progress" title="Rückmeldung wird erstellt …" />
          {:else if failed}
            <StatusMessage tone="error" title="Rückmeldung konnte nicht erstellt werden" description="Deine gespeicherte Bearbeitung bleibt erhalten." />
          {/if}
          {#if submission.feedback_md || submission.analysis_json?.criteria_results?.length}
            <div class="learning-submission-preview__details">
              {#if submission.feedback_md}
                <details class="learning-response-panel">
                  <summary>Rückmeldung</summary>
                  <div class="learning-response-panel__body markdown-prose">{@html renderMarkdown(submission.feedback_md)}</div>
                </details>
              {/if}
              {#if submission.analysis_json?.criteria_results?.length}
                <LearningCriteriaDetails label="Auswertung" criteria={submission.analysis_json.criteria_results} />
              {/if}
            </div>
          {/if}
        {:else if file}
          {#if isImage && !imageFailed}
            <img class="learning-submission-preview__image learning-submission-preview__image--compact" src={file.url} alt={`Eigene Bildabgabe zu ${taskTitle}`} loading="lazy" onerror={() => { imageFailed = true; }} />
          {/if}
          {#if imageFailed}<p class="workspace-note">Bild konnte nicht geladen werden.</p>{/if}
          <p class="learning-submission-preview__meta">{fileDescription()}</p>
        {:else if plainText}
          <p class="learning-submission-preview__text" use:measurePreview={plainText}>{plainText}</p>
        {:else if submission.kind === "h5p"}
          <p>Interaktive Bearbeitung gespeichert.</p>
        {:else if submission.kind === "dialog"}
          <p>Dialog gespeichert.</p>
        {:else}
          <p>Bearbeitung gespeichert.</p>
        {/if}
      </div>
      {#if canExpand || expanded}
        <div class="learning-submission-preview__actions">
          <button class="learning-submission-preview__toggle" type="button" aria-expanded={expanded} aria-controls={bodyId} onclick={() => { expanded = !expanded; }}>
            {expanded ? "Einklappen" : "Ausklappen"}
            <svg viewBox="0 0 16 16" aria-hidden="true" class:learning-submission-preview__chevron--open={expanded}><path d="m4 6 4 4 4-4" /></svg>
          </button>
        </div>
      {/if}
    </section>
    {#if submission.intent === "submit" && newerDraft}
      <div class="learning-submission-preview__draft">
        <span>Neuerer Entwurf vorhanden</span>
        <button class="workspace-top-action workspace-top-action--accent" type="button" onclick={() => onContinueDraft?.()}>Entwurf weiterbearbeiten</button>
      </div>
    {/if}
  {/if}
</div>
