<script lang="ts">
  import { renderMarkdown } from "$lib/utils/markdown";
  import LearningDialogTranscriptDocument from "$lib/components/learning-unit/LearningDialogTranscriptDocument.svelte";
  import StatusMessage from "$lib/components/ui/StatusMessage.svelte";
  import type { LearningMaterial, LearningSubmission } from "$lib/types/learning";

  let {
    referenceKey,
    label,
    title,
    material = null,
    submissions = [],
    expanded = true,
    readerMode = false,
    compact = false,
    courseId = null,
    taskId = null,
    onToggle = null,
    onOpenReader = null
  }: {
    referenceKey: string;
    label: string | null;
    title: string;
    material?: LearningMaterial | null;
    submissions?: LearningSubmission[];
    expanded?: boolean;
    readerMode?: boolean;
    compact?: boolean;
    courseId?: string | null;
    taskId?: string | null;
    onToggle?: ((referenceKey: string) => void) | null;
    onOpenReader?: ((referenceKey: string) => void) | null;
  } = $props();

  let failedImageUrls = $state<string[]>([]);

  const safeKey = $derived(referenceKey.replace(/[^a-zA-Z0-9_-]+/g, "-"));
  const bodyId = $derived(`reference-body-${safeKey}`);

  function orderedSubmissions(): LearningSubmission[] {
    return [...submissions].sort((left, right) => {
      const timeDifference = Date.parse(right.created_at) - Date.parse(left.created_at);
      return timeDifference || right.attempt_nr - left.attempt_nr;
    });
  }

  function primarySubmission(): LearningSubmission | null {
    const ordered = orderedSubmissions();
    return ordered.find((submission) => submission.intent === "submit") ?? ordered[0] ?? null;
  }

  function olderSubmissions(): LearningSubmission[] {
    const primaryId = primarySubmission()?.id;
    return orderedSubmissions().filter((submission) => submission.id !== primaryId);
  }

  function firstFile(submission: LearningSubmission | null): NonNullable<LearningSubmission["files"]>[number] | null {
    return submission?.files?.[0] ?? null;
  }

  function isImageMime(mime: string | null | undefined): boolean {
    return mime?.startsWith("image/") === true;
  }

  function isPdfMime(mime: string | null | undefined): boolean {
    return mime === "application/pdf";
  }

  function fileSize(size: number | null | undefined): string {
    if (!size || size <= 0) return "Datei";
    if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`;
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  }

  function markImageFailed(url: string): void {
    if (!failedImageUrls.includes(url)) {
      failedImageUrls = [...failedImageUrls, url];
    }
  }

  function imageFailed(url: string | null | undefined): boolean {
    return Boolean(url && failedImageUrls.includes(url));
  }

  function materialSummary(): string {
    if (!material?.body_md) return "Material zur Bearbeitung dieser Aufgabe.";
    const plain = material.body_md
      .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
      .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
      .replace(/^#{1,6}\s+(.+)$/gm, "$1 —")
      .replace(/[>*_`~|]+/g, " ")
      .replace(/\s+/g, " ")
      .replace(/\s+—\s*$/, "")
      .trim();
    return plain.length > 155 ? `${plain.slice(0, 152).trimEnd()} …` : plain;
  }

  function submissionDate(submission: LearningSubmission): string {
    return new Date(submission.created_at).toLocaleDateString("de-DE");
  }
</script>

<article
  class:learner-reference-document--reader={readerMode}
  class:learner-reference-document--compact={compact}
  class="learner-reference-document"
  aria-label={title}
>
  {#if readerMode}
    <header class="learner-reference-document__reader-header">
      {#if label}<p class="workspace-label">{label}</p>{/if}
      <h2 id="learner-reference-reader-heading" tabindex="-1">{title}</h2>
    </header>
  {:else}
    <header class="learner-reference-document__header">
      <button
        class="learner-reference-document__toggle"
        type="button"
        aria-label={`${title} ein- oder ausklappen`}
        aria-expanded={expanded}
        aria-controls={bodyId}
        onclick={() => onToggle?.(referenceKey)}
      >
        <svg
          class:learner-tree-chevron--expanded={expanded}
          class="learner-tree-chevron"
          aria-hidden="true"
          viewBox="0 0 16 16"
        >
          <path d="m6 3.5 4.5 4.5L6 12.5" />
        </svg>
        {#if compact}
          <svg class="learner-reference-document__type-icon" viewBox="0 0 24 28" aria-hidden="true">
            <path d="M5 2.5h9l5 5V25.5H5zM14 2.5v6h5M8.5 14h7M8.5 18h7" />
          </svg>
        {/if}
        <span>
          {#if label}<small>{label}</small>{/if}
          <strong>{title}</strong>
          {#if compact && !expanded}
            <span class="learner-reference-document__summary">{materialSummary()}</span>
          {/if}
        </span>
      </button>
      <div class="learner-reference-document__actions">
        {#if onOpenReader}
          <button
            id={`reference-reader-trigger-${safeKey}`}
            class="learner-reference-document__icon-action"
            type="button"
            title="Großansicht"
            aria-label={`${title} groß lesen`}
            onclick={() => onOpenReader?.(referenceKey)}
          >
            <svg aria-hidden="true" viewBox="0 0 24 24">
              <path d="M7 17 17 7M9 7h8v8" />
            </svg>
          </button>
        {/if}
      </div>
    </header>
  {/if}

  {#if expanded || readerMode}
    <div class="learner-reference-document__body" id={bodyId}>
      {#if material?.kind === "markdown"}
        <div class="learner-reference-document__prose markdown-prose">
          {@html renderMarkdown(material.body_md ?? "")}
        </div>
      {:else if material?.kind === "file"}
        <section class="learner-reference-document__file">
          {#if material.file_url && isImageMime(material.mime_type)}
            {#if imageFailed(material.file_url)}
              <StatusMessage tone="error" title="Bild nicht verfügbar" description="Das Bild konnte nicht geladen werden." />
            {:else}
              <img
                class="learner-reference-document__image"
                src={material.file_url}
                alt={material.alt_text?.trim() || `Material: ${material.title}`}
                loading="lazy"
                decoding="async"
                onerror={() => markImageFailed(material.file_url ?? "")}
              />
            {/if}
          {:else if material.file_url && isPdfMime(material.mime_type)}
            <iframe
              class="learner-reference-document__pdf"
              src={material.file_url}
              title={`Material ${material.title}`}
              loading="lazy"
            ></iframe>
          {:else}
            <p class="learner-reference-document__meta">
              {material.filename_original ?? material.mime_type ?? "Datei"} · {fileSize(material.size_bytes)}
            </p>
          {/if}
          {#if material.file_url}
            <a href={material.file_url} target="_blank" rel="noreferrer" aria-label={`${title} separat öffnen`}>
              Separat öffnen
            </a>
          {:else}
            <StatusMessage tone="error" title="Datei nicht verfügbar" description="Die Datei ist derzeit nicht verfügbar." />
          {/if}
        </section>
      {:else if primarySubmission()}
        {@const submission = primarySubmission()!}
        {@const file = firstFile(submission)}
        <section class="learner-reference-document__submission">
          <p class="learner-reference-document__meta">
            Eigene Abgabe · Versuch {submission.attempt_nr} · {submissionDate(submission)}
          </p>
          {#if submission.kind === "dialog" && submission.dialog_session_id && courseId && taskId}
            <LearningDialogTranscriptDocument
              {courseId}
              {taskId}
              sessionId={submission.dialog_session_id}
            />
          {/if}
          {#if submission.text_body}
            <div class="learner-reference-document__prose markdown-prose">
              {@html renderMarkdown(submission.text_body)}
            </div>
          {/if}
          {#if file && isImageMime(file.mime)}
            {#if imageFailed(file.url)}
              <StatusMessage tone="error" title="Bild nicht verfügbar" description="Das Bild konnte nicht geladen werden." />
            {:else}
              <img
                class="learner-reference-document__image"
                src={file.url}
                alt={`Eigene Bildabgabe zu ${title}`}
                loading="lazy"
                decoding="async"
                onerror={() => markImageFailed(file.url)}
              />
            {/if}
            <a href={file.download_url ?? file.url} target="_blank" rel="noreferrer">Bild separat öffnen</a>
          {:else if file && isPdfMime(file.mime)}
            <iframe
              class="learner-reference-document__pdf"
              src={file.url}
              title={`Eigene Abgabe zu ${title}`}
              loading="lazy"
            ></iframe>
            <a href={file.download_url ?? file.url} target="_blank" rel="noreferrer">Abgabe separat öffnen</a>
          {:else if file}
            <p class="learner-reference-document__meta">{file.mime} · {fileSize(file.size)}</p>
            <a href={file.download_url ?? file.url} target="_blank" rel="noreferrer">Abgabe öffnen</a>
          {/if}

          {#if submission.feedback_md}
            <details class="learner-reference-document__response">
              <summary>Rückmeldung</summary>
              <div class="learner-reference-document__prose markdown-prose">
                {@html renderMarkdown(submission.feedback_md)}
              </div>
            </details>
          {/if}
          {#if submission.analysis_json?.criteria_results?.length}
            <details class="learner-reference-document__response">
              <summary>Auswertung</summary>
              {#each submission.analysis_json.criteria_results as result}
                <section class="learner-reference-document__criterion">
                  <strong>{result.criterion}</strong>
                  {#if result.explanation_md}
                    <div class="learner-reference-document__prose markdown-prose">
                      {@html renderMarkdown(result.explanation_md)}
                    </div>
                  {/if}
                </section>
              {/each}
            </details>
          {/if}
          {#if olderSubmissions().length}
            <details class="learner-reference-document__response">
              <summary>Frühere Versuche</summary>
              {#each olderSubmissions() as older}
                <section class="learner-reference-document__older-attempt">
                  <strong>Versuch {older.attempt_nr} · {submissionDate(older)}</strong>
                  {#if older.text_body}
                    <div class="learner-reference-document__prose markdown-prose">
                      {@html renderMarkdown(older.text_body)}
                    </div>
                  {/if}
                </section>
              {/each}
            </details>
          {/if}
        </section>
      {:else}
        <p class="workspace-note">Der Inhalt wird geladen …</p>
      {/if}
    </div>
  {/if}
</article>
