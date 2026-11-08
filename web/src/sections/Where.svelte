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

  let {
    title,
    items,
    note = '',
    changeTitle = 'Change',
    inside,
    insideNote,
    memoryKey = '',
    empty = 'Nothing spent yet this month.',
  }: {
    title: string
    items: WhereItem[]
    note?: string
    changeTitle?: string
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
</script>

<div class="where" bind:clientWidth={width}>
  <Card {title} subtitle={items.length ? note : ''}>
    {#snippet actions()}
      {#if compared && items.length}
        <Segmented label="Change in" options={MODES} bind:value={mode} />
      {/if}
    {/snippet}
    {#if !items.length}
      <p class="caption">{empty}</p>
    {:else}
      {@render pair(main, inside ? (n: string) => (chosen = n) : undefined)}
    {/if}
  </Card>

  {#if inside && items.length && picked}
    <Card title="What's inside a category?">
      <Segmented label="Look inside" options={names} value={picked} onchange={(v) => (chosen = v)} />
      {#if !subItems.length}
        <p class="caption">Nothing in {picked} this month.</p>
      {:else}
        {#if insideNote}
          {@const text = insideNote(picked, subItems)}
          {#if text}<p class="caption">{text}</p>{/if}
        {/if}
        {@render pair(sub)}
      {/if}
    </Card>
  {/if}
</div>

{#snippet pair(data: ReturnType<typeof whereBars>, onpick?: (n: string) => void)}
  {#if data.changes}
    <div class="pair">
      <div>
        <div class="col-head">Spent</div>
        <RankedBars rows={data.bars} {onpick} />
      </div>
      <div>
        <div class="col-head">{changeTitle}</div>
        <ChangeBars rows={data.changes} />
      </div>
    </div>
  {:else}
    <RankedBars rows={data.bars} {onpick} />
  {/if}
{/snippet}

<style>
  .where { display: flex; flex-direction: column; gap: 1rem; }
  .pair { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 1.5rem; }
  .col-head { font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em;
    color: var(--ink-2); margin-bottom: 0.25rem; height: 1rem; }
</style>
