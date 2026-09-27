<script lang="ts">
  export type ChoiceSwitchOption = {
    value: string;
    label: string;
    disabled?: boolean;
  };

  let {
    legend,
    legendHidden = false,
    name,
    value,
    options,
    onValueChange
  }: {
    legend: string;
    legendHidden?: boolean;
    name: string;
    value: string;
    options: ChoiceSwitchOption[];
    onValueChange: (value: string) => void;
  } = $props();
</script>

<fieldset class="choice-switch">
  <legend class="choice-switch__legend" class:visually-hidden={legendHidden}>{legend}</legend>
  <div class="choice-switch__options">
    {#each options as option}
      <label class="choice-switch__option" data-current={option.value === value}>
        <input
          type="radio"
          {name}
          value={option.value}
          checked={option.value === value}
          disabled={option.disabled}
          onchange={() => onValueChange(option.value)}
        />
        <span>{option.label}</span>
      </label>
    {/each}
  </div>
</fieldset>

<style>
  .visually-hidden { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; border: 0; }
</style>
