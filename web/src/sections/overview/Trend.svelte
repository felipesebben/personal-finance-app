<!--
  How does each month compare? One column per month with its total written
  above it, the picked month brand green, a month in progress faded (never
  projected), and the usual month (average of three months logged in full)
  as a dashed line named at its end. 6 or 12 months, picked in the card.
-->
<script lang="ts">
  import Card from '../../lib/ui/Card.svelte'
  import Segmented from '../../lib/ui/Segmented.svelte'
  import Columns from '../../lib/charts/Columns.svelte'
  import { MUTED } from '../../lib/charts/palette'
  import { formatBrl, shortBrl } from '../../lib/money'
  import { monthLabel, monthlyTotals, ordinal, previousFullAverage } from '../../lib/overview/shaping'
  import type { OverviewContext } from './context'

  let { ctx, window = $bindable('12') }: { ctx: OverviewContext; window?: '6' | '12' } = $props()

  const trendMonths = $derived(ctx.months.slice(-Number(window)))
  const totals = $derived(monthlyTotals(ctx.rows, trendMonths, ctx.lens))
  const average = $derived(previousFullAverage(ctx.rows, ctx.months, ctx.selected, ctx.lens, 3, false, ctx.since))
  const starred = $derived(ctx.partlyMonth && trendMonths.includes(ctx.partlyMonth) ? ctx.partlyMonth : null)
  const columns = $derived(trendMonths.map((m) => {
    const partial = ctx.isPartial && m === ctx.selected
    const label = monthLabel(m, true) + (m === starred ? '*' : '')
    const v = totals.get(m) ?? 0
    return {
      label, value: v, picked: m === ctx.selected, partial,
      title: `${monthLabel(m)}: ${formatBrl(v)}${partial ? ' so far' : ''}${m === starred ? ' (logged in part)' : ''}`,
    }
  }))
  const references = $derived(average === null ? [] : [{ name: `Usual ${shortBrl(average)}`, value: average, color: MUTED }])
  const notes = $derived([
    ...(ctx.isPartial ? ['The faded month is still going: shown so far, never projected.'] : []),
    ...(starred && ctx.firstDate ? [`* ${monthLabel(starred)} was logged from the ${ordinal(Number(ctx.firstDate.slice(8, 10)))} only.`] : []),
    ...(average !== null ? ['Dashed line: the usual month, the average of the three before this one.'] : []),
  ])
</script>

<Card title="How does each month compare?">
  {#snippet actions()}
    <Segmented options={['6', '12']} bind:value={window} labels={{ '6': '6 months', '12': '12 months' }} />
  {/snippet}
  <Columns {columns} {references} height={290} />
  {#if notes.length}<p class="caption">{notes.join(' ')}</p>{/if}
</Card>
