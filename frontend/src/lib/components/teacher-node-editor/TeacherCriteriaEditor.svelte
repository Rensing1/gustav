<script lang="ts">
  let {
    initialValues = [],
    maxItems = 10
  }: {
    initialValues?: string[];
    maxItems?: number;
  } = $props();

  let criteria = $state<string[]>([""]);
  let initializedFrom = $state<string | null>(null);

  $effect(() => {
    const signature = JSON.stringify(initialValues);
    if (signature === initializedFrom) return;
    initializedFrom = signature;
    const restored = initialValues.slice(0, maxItems);
    criteria = restored.length ? restored : [""];
  });

  function addCriterion() {
    if (criteria.length < maxItems) criteria = [...criteria, ""];
  }

  function removeCriterion(index: number) {
    if (criteria.length === 1) {
      criteria = [""];
      return;
    }
    criteria = criteria.filter((_, itemIndex) => itemIndex !== index);
  }

  function moveCriterion(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= criteria.length) return;
    const next = [...criteria];
    [next[index], next[target]] = [next[target], next[index]];
    criteria = next;
  }
</script>

<fieldset class="workspace-field teacher-node-editor-criteria-fieldset">
  <legend>Kriterien</legend>
  <div class="teacher-node-editor-criteria-list teacher-node-editor-criteria-list--dynamic">
    {#each criteria as criterion, index}
      <div class="teacher-node-editor-criterion-row">
        <label class="workspace-field">
          <span>Kriterium {index + 1}</span>
          <input
            name="criteria[]"
            type="text"
            value={criterion}
            oninput={(event) => {
              criteria[index] = event.currentTarget.value;
              criteria = [...criteria];
            }}
          />
        </label>
        <div class="teacher-node-editor-criterion-actions" aria-label={`Kriterium ${index + 1} anordnen`}>
          <button type="button" aria-label={`Kriterium ${index + 1} nach oben`} disabled={index === 0} onclick={() => moveCriterion(index, -1)}>↑</button>
          <button type="button" aria-label={`Kriterium ${index + 1} nach unten`} disabled={index === criteria.length - 1} onclick={() => moveCriterion(index, 1)}>↓</button>
          <button type="button" aria-label={`Kriterium ${index + 1} entfernen`} onclick={() => removeCriterion(index)}>×</button>
        </div>
      </div>
    {/each}
  </div>
  {#if criteria.length < maxItems}
    <button class="workspace-link-action workspace-link-action--subtle" type="button" onclick={addCriterion}>Kriterium hinzufügen</button>
  {/if}
</fieldset>
