<script lang="ts">
  export type ChoiceSwitchOption = {
    value: string;
    label: string;
    disabled?: boolean;
  };

  let {
    legend,
    name,
    value,
    options,
    onValueChange
  }: {
    legend: string;
    name: string;
    value: string;
    options: ChoiceSwitchOption[];
    onValueChange: (value: string) => void;
  } = $props();
</script>

<fieldset class="choice-switch">
  <legend class="choice-switch__legend">{legend}</legend>
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
