<script lang="ts">
  import PageActionHead from "$lib/components/ui/PageActionHead.svelte";
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();

  const numberFormatter = new Intl.NumberFormat("de-DE");
  const usageLabels: Record<string, string> = {
    ocr: "OCR",
    analysis: "Analyse",
    feedback: "Rückmeldung",
    initial_starters: "Dialogstart",
    reply: "Dialogantwort"
  };

  function formatTokens(value: number | null | undefined): string {
    return numberFormatter.format(value ?? 0);
  }

  function unknownCallsLabel(count: number): string {
    return count === 1 ? "1 unbekannter Aufruf" : `${numberFormatter.format(count)} unbekannte Aufrufe`;
  }
</script>

<svelte:head>
  <title>KI-Nutzung · {data.usage.course.title} | GUSTAV</title>
</svelte:head>

<div class="workspace-page teacher-course-ai-usage">
  <PageActionHead
    backHref={data.usage.course.href}
    backLabel={`← ${data.usage.course.title}`}
    title="KI-Nutzung"
    copy="Input-, Output- und Gesamttokens des Kurses"
  />

  <form method="GET" class="teacher-course-ai-usage__filters" aria-label="KI-Nutzung filtern">
    <label>
      <span>Von</span>
      <input name="from_date" type="date" value={data.filterValues.fromDate} />
    </label>
    <label>
      <span>Bis</span>
      <input name="to_date" type="date" value={data.filterValues.toDate} />
    </label>
    <label>
      <span>Lerneinheit</span>
      <select name="unit_id" value={data.filterValues.unitId}>
        <option value="">Alle Lerneinheiten</option>
        {#each data.units as unit}
          <option value={unit.id}>{unit.title}</option>
        {/each}
      </select>
    </label>
    <div class="teacher-course-ai-usage__filter-actions">
      <button class="workspace-link-action" type="submit">Anwenden</button>
      <a class="workspace-text-button" href={`/teaching/courses/${data.usage.course.id}/ai-usage`}>Zurücksetzen</a>
    </div>
  </form>

  <section class="teacher-course-ai-usage__summary" aria-label="Tokenübersicht">
    <div>
      <span>Input</span>
      <strong>{formatTokens(data.usage.totals.input_tokens)}</strong>
    </div>
    <div>
      <span>Output</span>
      <strong>{formatTokens(data.usage.totals.output_tokens)}</strong>
    </div>
    <div>
      <span>Gesamt</span>
      <strong>{formatTokens(data.usage.totals.total_tokens)}</strong>
    </div>
  </section>

  {#if data.usage.totals.breakdown.length > 0}
    <section class="teacher-course-ai-usage__breakdown" aria-labelledby="usage-breakdown-title">
      <div class="teacher-course-ai-usage__section-head">
        <h2 id="usage-breakdown-title">Nutzung im Detail</h2>
        {#if data.usage.totals.unknown_events > 0}
          <p class="teacher-course-ai-usage__unknown">{unknownCallsLabel(data.usage.totals.unknown_events)}</p>
        {/if}
      </div>
      <div class="teacher-course-ai-usage__table-wrap">
        <table aria-label="Tokennutzung nach Modell und Nutzungsart">
          <thead>
            <tr>
              <th scope="col">Modell</th>
              <th scope="col">Nutzungsart</th>
              <th scope="col">Input</th>
              <th scope="col">Output</th>
              <th scope="col">Gesamt</th>
            </tr>
          </thead>
          <tbody>
            {#each data.usage.totals.breakdown as item}
              <tr>
                <th scope="row">{item.model}</th>
                <td>{usageLabels[item.stage] ?? item.stage}</td>
                <td>{formatTokens(item.input_tokens)}</td>
                <td>{formatTokens(item.output_tokens)}</td>
                <td>{formatTokens(item.total_tokens)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </section>
  {:else}
    <section class="teacher-course-ai-usage__empty" aria-labelledby="usage-empty-title">
      <h2 id="usage-empty-title">Noch keine Nutzung</h2>
      <p>Für diesen Kurs wurden noch keine LLM-Tokens erfasst.</p>
    </section>
  {/if}
</div>
