<script lang="ts">
  import { practiceCountLabel, practiceDueLabel } from "$lib/practice/practice-presentation";
  import type { LearningPracticeSession, LearningPracticeSessionSummary } from "$lib/types/practice";

  let {
    endReason,
    summary,
    nowIso
  }: {
    endReason: NonNullable<LearningPracticeSession["end_reason"]>;
    summary: LearningPracticeSessionSummary;
    nowIso: string;
  } = $props();

  const dueLabel = $derived(practiceDueLabel(summary.next_due_at, nowIso));
  const heading = $derived(
    endReason === "empty" ? "Heute ist nichts fällig" : endReason === "stopped" ? "Übung beendet" : "Übung geschafft"
  );
</script>

<section class="practice-summary" aria-labelledby="practice-summary-title">
  <header class="practice-summary__hero" data-tone={endReason === "completed" ? "success" : "neutral"}>
    <span class="practice-summary__icon" aria-hidden="true">
      {#if endReason === "completed"}✓{:else if endReason === "empty"}◷{:else}■{/if}
    </span>
    <p class="practice-eyebrow">Sitzungsabschluss</p>
    <h2 id="practice-summary-title">{heading}</h2>
    {#if endReason === "completed"}
      <p>Du hast deine ausgewählten Aufgaben bearbeitet. Deine Wiederholungen sind eingeplant.</p>
    {:else if endReason === "stopped"}
      <p>Deine bisherigen Antworten bleiben erhalten. Nicht bearbeitete Aufgaben wurden für diese Sitzung übersprungen.</p>
    {:else}
      <p>Für deine Auswahl stehen aktuell keine Wiederholungen an.</p>
    {/if}
  </header>

  {#if endReason !== "empty"}
    <div class="practice-summary__metrics" aria-label="Lernstände dieser Sitzung">
      <article><strong>{summary.classification_counts.secure}</strong><span>Sicher</span></article>
      <article><strong>{summary.classification_counts.partial}</strong><span>Teilweise</span></article>
      <article><strong>{summary.classification_counts.insufficient}</strong><span>Noch üben</span></article>
    </div>

    <div class="practice-summary__details">
      <p>{practiceCountLabel(summary.answered_items, "Aufgabe bearbeitet", "Aufgaben bearbeitet")}</p>
      <p>{practiceCountLabel(summary.skipped_items, "Aufgabe übersprungen", "Aufgaben übersprungen")}</p>
      {#if summary.pending_items > 0}
        <p class="practice-summary__pending" role="status" aria-live="polite">Auswertung wird abgeschlossen</p>
      {/if}
      {#if dueLabel}<p class="practice-summary__due">{dueLabel}</p>{/if}
    </div>
  {/if}

  <div class="practice-summary__actions">
    {#if endReason === "empty"}
      <a class="practice-button practice-button--primary" href="/learning/practice?mode=exam">Alle Aufgaben üben</a>
      <a class="practice-button practice-button--secondary" href="/learning">Zum Lernraum</a>
    {:else}
      <a class="practice-button practice-button--primary" href="/learning/practice">
        {endReason === "stopped" ? "Neue Übung auswählen" : "Weitere Themen üben"}
      </a>
      <a class="practice-button practice-button--secondary" href="/learning">Zum Lernraum</a>
    {/if}
  </div>
</section>
