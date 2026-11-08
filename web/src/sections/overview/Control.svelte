<!--
  Are the costs we control changing? Day-to-day spending and bills that
  vary (cost type Variable), one-offs left out, each category against its
  usual month: the answer in sentences first, then a small KPI per category
  with its months as sparkbars and the usual month as a dashed line.
-->
<script lang="ts">
  import Card from '../../lib/ui/Card.svelte'
  import Legend from '../../lib/charts/Legend.svelte'
  import Kpi from '../../lib/ui/Kpi.svelte'
  import MonthSpark from '../../lib/charts/MonthSpark.svelte'
  import { formatBrl } from '../../lib/money'
  import { controlLines, controlRows, deltaLine, type Line } from '../../lib/overview/shaping'
  import { sparkBars, type OverviewContext } from './context'
  import Lines from './Lines.svelte'

  let { ctx }: { ctx: OverviewContext } = $props()

  const CONTROL_CARDS = 9
  const rows = $derived(controlRows(ctx.rows, ctx.months, ctx.selected, ctx.lens, ctx.isPartial, ctx.since))
  const shown = $derived(rows.slice(0, CONTROL_CARDS))
  const lines = (r: (typeof rows)[number]): Line[] => [
    r.usual === null ? ['No usual month yet', null] : deltaLine(r.change ?? 0, r.pct, 'usual'),
    ...(r.streak >= 2 ? [[`${r.streak} months above usual`, null] as Line] : []),
  ]
</script>

<Card title="Are the costs we control changing?"
  subtitle={'Day-to-day spending and bills that vary (cost type Variable in Settings), one-offs left out, each against its usual month' +
    (ctx.isPartial ? ' over the same days' : '') + '.'}>
  {#if !rows.length}
    <p class="caption">Nothing here among what's being counted: the filters may leave it out.</p>
  {:else}
    <Lines lines={controlLines(rows)} />
    <div class="grid cols-3 small">
      {#each shown as r (r.name)}
        <div class="mini">
          <Kpi label={r.name} value={formatBrl(r.current)} lines={lines(r)} />
          <MonthSpark bars={sparkBars(new Map(r.series), ctx, formatBrl)} reference={r.usual}
            referenceName={r.usual === null ? '' : `Usual: ${formatBrl(r.usual)}`} height={64} />
        </div>
      {/each}
    </div>
    <Legend items={[{ mark: 'dash', label: 'Usual month' }, ...(ctx.isPartial ? [{ mark: 'partial' as const, label: 'This month so far' }] : [])]} />
    {#if rows.length > CONTROL_CARDS}
      <p class="caption">The {CONTROL_CARDS} biggest of {rows.length}; Filters › Categories narrows it.</p>
    {/if}
  {/if}
</Card>

<style>
  .small { gap: 1.25rem 1.5rem; margin-top: 0.5rem; }
  .mini { display: flex; flex-direction: column; padding-top: 0.75rem; border-top: 1px solid var(--hairline); }
  .mini :global(.value) { font-size: 1.35rem; }
</style>
