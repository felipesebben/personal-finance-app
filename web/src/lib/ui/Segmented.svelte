<!-- A pill row: pick one of a few options (what to count, a category to look inside). -->
<script lang="ts" generics="T extends string">
  let { options, value = $bindable(), label = '', labels = {}, onchange }: {
    options: T[]
    value: T
    label?: string
    labels?: Record<string, string>
    onchange?: (v: T) => void
  } = $props()
</script>

<div class="field">
  {#if label}<span>{label}</span>{/if}
  <div class="pills" role="radiogroup" aria-label={label || undefined}>
    {#each options as option}
      <button type="button" role="radio" aria-checked={value === option} class:active={value === option}
        onclick={() => { value = option; onchange?.(option) }}>{labels[option] ?? option}</button>
    {/each}
  </div>
</div>

<style>
  .pills { display: flex; flex-wrap: wrap; gap: 0.35rem; }
  button { border: 1px solid var(--line); background: var(--surface); border-radius: 999px; padding: 0.4rem 0.85rem;
    min-height: 2.3rem; cursor: pointer; font-size: 0.9rem; color: var(--ink); }
  button:hover { border-color: var(--brand); }
  button.active { background: var(--brand); border-color: var(--brand); color: #fff; }
</style>
