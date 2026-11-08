<!--
  Three equal cards, each a number, its comparison and its months as
  sparkbars: the total against last month (same days while the month is
  going), the usual month (the three before, logged in full) with this month
  set against it, and the category that rose most. A ▲/▼ only against a
  month logged in full; a partly logged one is named instead.
  (The expense-count card was dropped: how many expenses says little.)
-->
<script lang="ts">
  import Card from '../../lib/ui/Card.svelte'
  import Kpi from '../../lib/ui/Kpi.svelte'
  import EmptyChart from '../../lib/ui/EmptyChart.svelte'
  import MonthSpark from '../../lib/charts/MonthSpark.svelte'
  import { SPARK_HEIGHT } from '../../lib/charts/palette'
  import { formatBrl } from '../../lib/money'
  import {
    biggestIncrease, compare, compareTotal, deltaLine, monthLabel, monthlyTotals, ordinal, previousFullAverage,
    shiftMonth, type Line,
  } from '../../lib/overview/shaping'
  import { sparkBars, type OverviewContext } from './context'

  let { ctx }: { ctx: OverviewContext } = $props()

  const MIN = 250
  const shown = $derived(ctx.months.slice(-6))
  const total = $derived(compareTotal(ctx.rows, ctx.selected, ctx.isPartial, ctx.lens))
  const average = $derived(previousFullAverage(ctx.rows, ctx.months, ctx.selected, ctx.lens, 3, ctx.isPartial, ctx.since))
  const comparison = $derived(compare(ctx.rows, ctx.selected, ctx.isPartial, ctx.lens))
  const rising = $derived(ctx.comparable ? biggestIncrease(comparison) : null)
  const toDate = $derived(ctx.isPartial ? ' so far' : '')

  const totalLine = $derived.by((): Line => {
    if (ctx.comparable) return deltaLine(total.change, total.pct, ctx.previousTitle)
    if (ctx.partly) {
      const whole = monthlyTotals(ctx.rows, [ctx.previous], ctx.lens).get(ctx.previous) ?? 0
      return [`${monthLabel(ctx.previous, true)}: ${formatBrl(whole)}, logged from the ${ordinal(ctx.partly)} only`, null]
    }
    return ['Compared once a whole month has been logged', null]
  })

  // The usual months (same days while going) and this month beside them, against the dashed average.
  const usualBars = $derived.by(() => {
    const usual = [3, 2, 1].map((k) => shiftMonth(ctx.selected, -k))
    const values = monthlyTotals(ctx.rows, usual, ctx.lens, ctx.isPartial)
    values.set(ctx.selected, total.current)
    return sparkBars(values, ctx, formatBrl)
  })

  const risingRow = $derived(rising ? comparison.find((c) => c.key === rising) ?? null : null)
  const risingBars = $derived(rising
    ? sparkBars(monthlyTotals(ctx.rows.filter((r) => r.primary_category === rising), shown, ctx.lens), ctx, formatBrl)
    : [])
</script>

<div class="grid cols-3 kpis">
  <Card minHeight={MIN}>
    <Kpi label="{ctx.headline}{toDate}" value={formatBrl(total.current)} lines={[totalLine]}
      help={`Everything counted in the month${ctx.isPartial ? ', up to today' : ''}.`} />
    <MonthSpark bars={sparkBars(monthlyTotals(ctx.rows, shown, ctx.lens), ctx, formatBrl)} />
  </Card>

  <Card minHeight={MIN}>
    {#if average === null}
      <Kpi label="Usual month" value="—" lines={[[`Needs three full months of ${ctx.noun} first.`, null]]}
        help="The average of the three months before this one, logged in full." />
      <EmptyChart text="Appears once there's history to compare with." height={SPARK_HEIGHT} />
    {:else}
      <Kpi label={`Usual month${ctx.isPartial ? ' (same days)' : ''}`} value={formatBrl(average)}
        lines={[deltaLine(total.current - average, average ? (total.current - average) / average : null, 'it')]}
        help="The average of the three months before this one, over the same days while this month is going. The dashed line marks it." />
      <MonthSpark bars={usualBars} reference={average} referenceName={`Usual month: ${formatBrl(average)}`} />
    {/if}
  </Card>

  <Card minHeight={MIN}>
    {#if !ctx.comparable}
      <Kpi label="Biggest increase" value="—" lines={[['Compared once a whole month has been logged.', null]]}
        help="The category that rose most in reais against last month." />
      <EmptyChart text="Appears once there's history to compare with." height={SPARK_HEIGHT} />
    {:else if !rising || !risingRow}
      <Kpi label="Biggest increase" value="—" lines={[[`Nothing rose against ${ctx.previousTitle}.`, 'less']]}
        help="The category that rose most in reais against last month." />
      <EmptyChart text="Nothing rose." height={SPARK_HEIGHT} />
    {:else}
      <Kpi label="Biggest increase" value={rising} lines={[deltaLine(risingRow.change, risingRow.pct, ctx.previousTitle)]}
        help="The category that rose most in reais against last month." />
      <MonthSpark bars={risingBars} />
    {/if}
  </Card>
</div>

<style>
  .kpis :global(.card) { justify-content: flex-start; }
</style>
