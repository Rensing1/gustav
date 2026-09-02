<script lang="ts">
  import {
    criterionLevel,
    type CriterionLevel,
    type LearningCriterionResult
  } from "$lib/learning-unit/criterion-level";
  import { renderMarkdown } from "$lib/utils/markdown";

  let {
    criteria,
    label = "Kriterien im Detail",
    open = false
  }: {
    criteria: LearningCriterionResult[];
    label?: string;
    open?: boolean;
  } = $props();

  const levelClass: Record<CriterionLevel, string> = {
    "Mangelhaft": "learning-criterion__level--mangelhaft",
    "Ansatzweise": "learning-criterion__level--ansatzweise",
    "Gelungen": "learning-criterion__level--gelungen",
    "Hervorragend": "learning-criterion__level--hervorragend",
    "Ohne Einstufung": "learning-criterion__level--ohne-einstufung"
  };
</script>

<details class="learning-criteria-details" {open}>
  <summary>
    <span class="learning-criteria-details__summary-copy">
      <span>{label}</span>
      <span class="learning-criteria-details__count">{criteria.length} {criteria.length === 1 ? "Kriterium" : "Kriterien"}</span>
    </span>
  </summary>
  <ul class="learning-criteria-details__list" aria-label="Bewertungskriterien">
    {#each criteria as criterion, index}
      {@const level = criterionLevel(criterion.score, criterion.max_score)}
      <li class="learning-criteria-details__item">
        <details class="learning-criterion">
          <summary>
            <span class="learning-criterion__index" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
            <span class="learning-criterion__title">{criterion.criterion}</span>
            <span class={`learning-criterion__level ${levelClass[level]}`}>{level}</span>
          </summary>
          {#if criterion.explanation_md}
            <div class="learning-criterion__explanation markdown-prose">
              {@html renderMarkdown(criterion.explanation_md)}
            </div>
          {/if}
        </details>
      </li>
    {/each}
  </ul>
</details>
