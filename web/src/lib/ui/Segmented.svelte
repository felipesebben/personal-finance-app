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
  <div class="pills" class:seg={options.length <= 4} role="radiogroup" aria-label={label || undefined}>
    {#each options as option}
      <button type="button" role="radio" aria-checked={value === option} class:active={value === option}
        onclick={() => { value = option; onchange?.(option) }}>{labels[option] ?? option}</button>
    {/each}
  </div>
</div>

<style>
  /* Up to four options: a segmented control. More (e.g. categories): capsule chips that wrap. */
  .pills { display: inline-flex; flex-wrap: wrap; gap: 0.4rem; max-width: 100%; }
  .pills.seg { align-self: flex-start; gap: 2px; padding: 2px; background: var(--fill); border-radius: 9px; flex-wrap: nowrap;
    overflow-x: auto; scrollbar-width: none; }
  button { border: none; background: var(--fill); border-radius: 999px; padding: 0.4rem 0.9rem;
    min-height: 2.1rem; cursor: pointer; font-size: 0.875rem; font-weight: 500; color: var(--ink);
    transition: background 0.2s ease, box-shadow 0.2s ease, color 0.2s ease; white-space: nowrap; }
  button:hover:not(.active) { filter: brightness(0.97); }
  button.active { background: var(--brand); color: var(--on-brand); font-weight: 600; }
  .seg button { background: none; border-radius: 7px; min-height: 1.95rem; padding: 0.3rem 0.95rem; flex: 1 0 auto; }
  .seg button.active { background: var(--thumb); color: var(--ink);
    box-shadow: 0 3px 8px rgba(0, 0, 0, 0.12), 0 3px 1px rgba(0, 0, 0, 0.04); }
</style>
