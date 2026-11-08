<!--
  Pick one of a few options. Up to four: an iOS segmented control; more: capsule chips that wrap.
  `compact` is for toolbars and a card's top-right corner (a chart's own picker): small and quiet, with the
  label kept for screen readers only, as Apple's toolbars do. Forms use the regular size with a visible label.
-->
<script lang="ts" generics="T extends string">
  let { options, value = $bindable(), label = '', labels = {}, onchange, compact = false }: {
    options: T[]
    value: T
    label?: string
    labels?: Record<string, string>
    onchange?: (v: T) => void
    compact?: boolean
  } = $props()
</script>

<div class="field" class:compact>
  {#if label}<span class:sr-only={compact}>{label}</span>{/if}
  <div class="pills" class:seg={options.length <= 4} role="radiogroup" aria-label={label || undefined}>
    {#each options as option}
      <button type="button" role="radio" aria-checked={value === option} class:active={value === option}
        onclick={() => { value = option; onchange?.(option) }}>{labels[option] ?? option}</button>
    {/each}
  </div>
</div>

<style>
  .pills { display: inline-flex; flex-wrap: wrap; gap: 0.4rem; max-width: 100%; }
  .pills.seg { align-self: flex-start; gap: 2px; padding: 2px; background: var(--fill); border-radius: 9px; flex-wrap: nowrap;
    overflow-x: auto; scrollbar-width: none; }
  button { border: none; background: var(--fill); border-radius: 999px; padding: 0.4rem 0.9rem;
    min-height: 2.1rem; cursor: pointer; font-size: var(--t-subhead); font-weight: 400; color: var(--ink);
    transition: background 0.2s ease, box-shadow 0.2s ease, color 0.2s ease; white-space: nowrap; }
  button:hover:not(.active) { filter: brightness(0.97); }
  button.active { background: var(--brand); color: var(--on-brand); font-weight: 500; }
  .seg button { background: none; border-radius: 7px; min-height: 1.95rem; padding: 0.3rem 0.95rem; flex: 1 0 auto; }
  .seg button.active { background: var(--thumb); color: var(--ink);
    box-shadow: 0 3px 8px rgba(0, 0, 0, 0.12), 0 3px 1px rgba(0, 0, 0, 0.04); }

  /* Compact: a control that stays out of the data's way. */
  .compact .pills.seg { border-radius: 8px; }
  .compact button { min-height: 1.75rem; padding: 0.15rem 0.7rem; font-size: var(--t-footnote); }
  .compact .seg button { min-height: 1.6rem; border-radius: 6px; padding: 0.1rem 0.75rem; }
</style>
