<!--
  A KPI: small spaced-capital label, the number, then ▲/▼ lines as
  [text, tone] with tone "more" (orange), "less" (blue) or "" (ink). The text
  carries its own arrow, so colour is never alone. `help` shows as a tooltip
  and as an (i) that can be tapped on a phone. Children go under (a sparkline).
-->
<script lang="ts">
  import type { Snippet } from 'svelte'
  let { label, value, lines = [], hero = false, help = '', children }: {
    label: string
    value: string
    lines?: [string, string | null][]
    hero?: boolean
    help?: string
    children?: Snippet
  } = $props()
  let open = $state(false)
</script>

<div class="kpi" class:hero>
  <div class="label">
    <span>{label}</span>
    {#if help}
      <button type="button" class="help" title={help} aria-label="What this means" aria-expanded={open}
        onclick={() => (open = !open)}>i</button>
    {/if}
  </div>
  {#if open && help}<p class="help-text">{help}</p>{/if}
  <div class="value">{value}</div>
  {#each lines as [text, tone]}
    <div class="line {tone ?? ''}">{text}</div>
  {/each}
  {@render children?.()}
</div>

<style>
  .kpi { line-height: 1.3; min-width: 0; }
  .label { display: flex; align-items: center; gap: 0.35rem; color: var(--ink-2); font-size: 0.72rem;
    font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; }
  .hero .label { color: var(--ink); font-size: 1rem; text-transform: none; letter-spacing: 0; }
  .help { width: 1.05rem; height: 1.05rem; border-radius: 50%; border: 1px solid var(--line); background: none;
    font-size: 0.65rem; font-weight: 700; color: var(--muted); cursor: pointer; padding: 0; line-height: 1;
    text-transform: none; }
  .help-text { font-size: 0.8rem; color: var(--ink-2); margin: 0.3rem 0; }
  .value { font-size: 1.75rem; font-weight: 700; white-space: nowrap; margin: 0.15rem 0 0.25rem;
    font-variant-numeric: proportional-nums; letter-spacing: -0.01em; }
  .hero .value { font-size: 2.75rem; line-height: 1.1; letter-spacing: -0.02em; margin: 0.2rem 0 0.35rem; }
  .line { font-size: 0.85rem; color: var(--ink-2); }
  .hero .line { font-size: 0.92rem; }
  .line.more { color: var(--more); font-weight: 600; }
  .line.less { color: var(--less); font-weight: 600; }
  @media (max-width: 560px) {
    .hero .value { font-size: 2.2rem; }
  }
</style>
