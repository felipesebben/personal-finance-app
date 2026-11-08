<!--
  Where the money goes, as the analysis views draw it: two cards.
  1. "Where is the money going?": ranked bars (a grey tick at the comparison,
     a dark tick at the target) with the change beside each bar, in R$ or %
     ("Change in"). On a narrow screen the change can't sit beside its bar,
     so it moves into the bar's tip ("R$ 1,2 mil · ▲ 33%").
  2. "What's inside a category?": a pill row picks the category (also a tap
     on its bar above), then its sub-categories drawn the same way.
  Reusable: pass the categories as WhereItem[] and, for the second card, an
  `inside(category)` that returns its sub-categories.
-->
<script lang="ts" module>
  import type { ChangeMode } from '../lib/daily/where'
  // Remembered per `memoryKey` while the app is open, so switching tabs keeps the picks.
  const memory = new Map<string, { mode: ChangeMode; picked: string | null }>()
</script>

<script lang="ts">
  import { untrack } from 'svelte'
  import { MODES, whereBars, type WhereItem } from '../lib/daily/where'
  import Card from '../lib/ui/Card.svelte'
  import Segmented from '../lib/ui/Segmented.svelte'
  import RankedBars from '../lib/charts/RankedBars.svelte'
  import ChangeBars from '../lib/charts/ChangeBars.svelte'
  import Legend, { type LegendItem } from '../lib/charts/Legend.svelte'
  import { shortBrl } from '../lib/money'

  let {
    title,
    items,
    note = '',
    changeTitle = 'Change',
    tickLabel = 'Last month',
    targetLabel = 'Monthly target',
    subTargetLabel = 'Sub-category target',
    inside,
    insideNote,
    memoryKey = '',
    empty = 'Nothing spent yet this month.',
  }: {
    title: string
    items: WhereItem[]
    note?: string
    changeTitle?: string
    /** Legend names for the grey tick (the comparison) and the dark tick (the target). */
    tickLabel?: string
    targetLabel?: string
    subTargetLabel?: string
    inside?: (category: string) => WhereItem[]
    insideNote?: (category: string, items: WhereItem[]) => string
    memoryKey?: string
    empty?: string
  } = $props()

  // The picks this view had when it was last shown (read once, on mount).
  const remembered = untrack(() => memory.get(memoryKey))
  let mode = $state<ChangeMode>(remembered?.mode ?? 'R$')
  let chosen = $state<string | null>(remembered?.picked ?? null)
  let width = $state(800)

  const names = $derived(items.map((i) => i.name))
  const picked = $derived(chosen && names.includes(chosen) ? chosen : (names[0] ?? null))
  const narrow = $derived(width < 640)
  const compared = $derived(items.some((i) => i.previous !== null && i.previous !== undefined))
  const main = $derived(whereBars(items, mode, inside ? picked : null, narrow))
  const subItems = $derived(inside && picked ? inside(picked) : [])
  const sub = $derived(whereBars(subItems, mode, null, narrow))

  $effect(() => {
    if (memoryKey) memory.set(memoryKey, { mode, picked: chosen })
  })

  // The change axis in the unit picked: "+R$ 500" or "+20%".
  const changeFormat = $derived((v: number) => {
    const sign = v > 0 ? '+' : v < 0 ? '−' : ''
    return mode === '%' ? `${sign}${Math.round(Math.abs(v) * 100)}%` : `${sign}${shortBrl(Math.abs(v))}`
  })
  // A legend for the marks that aren't labelled where they are.
  const legendFor = (data: ReturnType<typeof whereBars>, target: string): LegendItem[] => [
    ...(data.bars.some((b) => b.tick) ? [{ mark: 'tick' as const, label: tickLabel }] : []),
    ...(data.bars.some((b) => b.target) ? [{ mark: 'target' as const, label: target }] : []),
  ]
</script>

<div class="where" bind:clientWidth={width}>
  <Card {title} subtitle={items.length ? note : ''}>
    {#snippet actions()}
      {#if compared && items.length}
        <Segmented compact label="Change in" options={MODES} bind:value={mode} />
      {/if}
    {/snippet}
    {#if !items.length}
      <p class="caption">{empty}</p>
    {:else}
      {@render pair(main, inside ? (n: string) => (chosen = n) : undefined)}
      <Legend items={legendFor(main, targetLabel)} />
    {/if}
  </Card>

  {#if inside && items.length && picked}
    <Card title="What's inside a category?">
      {#snippet actions()}
        {#if names.length <= 4}
          <Segmented compact label="Look inside" options={names} value={picked} onchange={(v) => (chosen = v)} />
        {:else}
          <label class="field">
            <span class="sr-only">Look inside</span>
            <select class="compact" value={picked} onchange={(e) => (chosen = e.currentTarget.value)}>
              {#each names as n}<option value={n}>{n}</option>{/each}
            </select>
          </label>
        {/if}
      {/snippet}
      {#if !subItems.length}
        <p class="caption">Nothing in {picked} this month.</p>
      {:else}
        {#if insideNote}
          {@const text = insideNote(picked, subItems)}
          {#if text}<p class="caption">{text}</p>{/if}
        {/if}
        {@render pair(sub)}
        <Legend items={legendFor(sub, subTargetLabel)} />
      {/if}
    </Card>
  {/if}
</div>

{#snippet pair(data: ReturnType<typeof whereBars>, onpick?: (n: string) => void)}
  {#if data.changes}
    <div class="pair">
      <div>
        <div class="col-head">Spent</div>
        <RankedBars rows={data.bars} {onpick} description="Bar chart of what was spent" />
      </div>
      <div>
        <div class="col-head">{changeTitle}</div>
        <ChangeBars rows={data.changes} format={changeFormat} />
      </div>
    </div>
  {:else}
    <RankedBars rows={data.bars} {onpick} />
  {/if}
{/snippet}

<style>
  .where { display: flex; flex-direction: column; gap: 1rem; }
  .pair { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 1.5rem; }
  .col-head { font-size: var(--t-footnote); font-weight: 400;
    color: var(--muted); margin-bottom: 0.25rem; height: 1rem; }
</style>
