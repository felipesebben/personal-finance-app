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
  {#if lines.length}
    <div class="lines">
      {#each lines as [text, tone]}<div class="line {tone ?? ''}">{text}</div>{/each}
    </div>
  {/if}
  {@render children?.()}
</div>

<style>
  .kpi { line-height: 1.3; min-width: 0; }
  .label { display: flex; align-items: center; gap: 0.35rem; color: var(--muted); font-size: 0.8125rem;
    font-weight: 600; letter-spacing: -0.005em; }
  .hero .label { color: var(--ink); font-size: 1.0625rem; }
  .help { width: 1.1rem; height: 1.1rem; border-radius: 50%; border: none; background: var(--fill);
    font-size: 0.68rem; font-weight: 700; color: var(--muted); cursor: pointer; padding: 0; line-height: 1;
    font-family: Georgia, serif; font-style: italic; }
  .help[aria-expanded='true'] { background: var(--brand-soft); color: var(--brand); }
  .help-text { font-size: 0.8125rem; color: var(--ink-2); margin: 0.3rem 0; }
  /* The number leads: large, bold, proportional digits at display size. */
  .value { font-family: var(--font-display); font-size: 1.75rem; font-weight: 700; white-space: nowrap;
    margin: 0.2rem 0 0.25rem; font-variant-numeric: proportional-nums; letter-spacing: -0.02em; }
  .hero .value { font-size: 2.75rem; line-height: 1.1; letter-spacing: -0.03em; margin: 0.25rem 0 0.35rem; }
  /* Context under the number stays quiet (secondary label colour, regular weight), one short line each. */
  .lines { display: flex; flex-direction: column; gap: 0.1rem; margin-top: 0.1rem; }
  .line { font-size: 0.8125rem; color: var(--muted); text-wrap: pretty; }
  .hero .line { font-size: 0.875rem; }
  .line.more { color: var(--more); font-weight: 500; }
  .line.less { color: var(--less); font-weight: 500; }
  @media (max-width: 560px) {
    .hero .value { font-size: 2.25rem; }
  }
</style>
