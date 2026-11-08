<!--
  Two compact cards side by side. Fixed costs: the month's total and which
  ones moved (a price rise shows here). One-offs: annual and extraordinary
  costs this month, the biggest named, then how much to set aside a month
  for them and the annual bills coming round again.
-->
<script lang="ts">
  import Card from '../../lib/ui/Card.svelte'
  import Kpi from '../../lib/ui/Kpi.svelte'
  import { formatBrl, signedBrl } from '../../lib/money'
  import {
    biggestChanges, compare, compareTotal, deltaLine, fixedCosts, lensColumn, oneOffs, reserve, reserveLines,
    type Line,
  } from '../../lib/overview/shaping'
  import type { OverviewContext } from './context'

  let { ctx }: { ctx: OverviewContext } = $props()

  const fixed = $derived(fixedCosts(ctx.rows))
  const fixedTotal = $derived(compareTotal(fixed, ctx.selected, ctx.isPartial, ctx.lens))
  const fixedLines = $derived.by((): Line[] => {
    if (!ctx.comparable) return fixed.length ? [] : [['No fixed costs among what\'s being counted.', null]]
    const moved = biggestChanges(compare(fixed, ctx.selected, ctx.isPartial, ctx.lens, 'sub_category')).slice(0, 3)
    return [
      deltaLine(fixedTotal.change, fixedTotal.pct, ctx.previousTitle),
      ...moved.map((r): Line => [`${r.key}: ${r.change > 0 ? '▲' : '▼'} ${signedBrl(r.change)}`, r.change > 0 ? 'more' : 'less']),
    ]
  })

  const col = $derived(lensColumn(ctx.lens))
  const thisMonth = $derived(oneOffs(ctx.rows).filter((r) => r.month === ctx.selected))
  const offsTotal = $derived(thisMonth.reduce((s, r) => s + r[col], 0))
  const offsLines = $derived.by((): Line[] => {
    const bySub = new Map<string, number>()
    for (const r of thisMonth) bySub.set(r.sub_category, (bySub.get(r.sub_category) ?? 0) + r[col])
    const biggest = [...bySub.entries()].filter(([, v]) => v).sort((a, b) => b[1] - a[1]).slice(0, 3)
      .map(([name, v]): Line => [`${name}: ${formatBrl(v)}`, null])
    return [...(biggest.length ? biggest : [['None this month', null] as Line]),
      ...reserveLines(reserve(ctx.rows, ctx.months, ctx.selected, ctx.lens, ctx.since))]
  })
</script>

<div class="grid cols-2">
  <Card minHeight={160}>
    <Kpi label={`Fixed costs${ctx.isPartial ? ' so far' : ''}`} value={formatBrl(fixedTotal.current)} lines={fixedLines}
      help="What recurs at a set price: rent, condo, internet, subscriptions, insurance. One-offs are counted apart. A bill not logged yet this month shows as a drop." />
  </Card>
  <Card minHeight={160}>
    {#if ctx.filters.withoutOneOffs}
      <Kpi label="One-offs" value="—" lines={[['Left out by the filters', null]]} />
    {:else}
      <Kpi label="One-offs" value={formatBrl(offsTotal)} lines={offsLines}
        help="Annual and extraordinary costs (IPVA, a vet emergency): counted apart, since they say little about how you live. The amount to set aside is what they averaged per month over the months logged in full, rounded up to R$ 50." />
    {/if}
  </Card>
</div>
