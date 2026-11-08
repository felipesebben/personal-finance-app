<!--
  Monthly columns: one per month, the picked month brand green and the rest
  a lighter green, a month in progress faded with a dashed outline (never
  projected), each total written above its column, and optional dashed
  reference lines (the usual month, the 12-month average, the target) named
  at their right end. Values in cents.
-->
<script lang="ts">
  import { scaleBand, scaleLinear } from 'd3-scale'
  import { AXIS, BRAND, BRAND_LIGHT, BRAND_PALE, GRID, INK_2, MUTED, barPath, textWidth } from './palette'
  import { formatBrl, shortBrl } from '../money'

  export interface Column {
    label: string
    value: number
    picked?: boolean
    partial?: boolean
    title?: string
  }
  export interface Reference {
    name: string
    value: number
    color?: string
    dash?: string
  }

  let { columns, references = [], height = 220 }: {
    columns: Column[]
    references?: Reference[]
    height?: number
  } = $props()

  let width = $state(480)
  const right = $derived(references.length ? Math.max(...references.map((r) => textWidth(r.name, 11))) + 10 : 6)
  const max = $derived(Math.max(...columns.map((c) => c.value), ...references.map((r) => r.value), 1))
  // The y axis on the leading edge: a few round values in short reais, so the grid lines read as amounts.
  const yTicks = $derived(scaleLinear().domain([0, max * 1.08]).ticks(3).filter((t) => t > 0))
  const left = $derived(Math.max(...yTicks.map((t) => textWidth(shortBrl(t), 11)), 0) + 8)
  const margin = $derived({ top: 18, right, bottom: 24, left })
  const x = $derived(scaleBand<string>().domain(columns.map((c) => c.label)).range([margin.left, width - margin.right])
    .paddingInner(0.25).paddingOuter(0.1))
  const y = $derived(scaleLinear().domain([0, max * 1.08]).range([height - margin.bottom, margin.top]))
  const showValues = $derived(x.bandwidth() > 34)
  // Thin the month labels when they'd collide.
  const every = $derived(Math.max(1, Math.ceil((Math.max(...columns.map((c) => textWidth(c.label, 11)), 1) + 6) / Math.max(x.step(), 1))))
  const refLabels = $derived.by(() => {
    const items = references.map((r) => ({ ...r, y: y(r.value) })).sort((a, b) => a.y - b.y)
    for (let i = 1; i < items.length; i++) if (items[i].y - items[i - 1].y < 13) items[i].y = items[i - 1].y + 13
    return items
  })
</script>

<div class="wrap" bind:clientWidth={width}>
  <svg {width} {height} role="img" aria-label="Column chart, one column per month{references.length ? `, with ${references.map((r) => r.name).join(' and ')} as reference lines` : ''}. {columns.map((c) => `${c.label}: ${formatBrl(c.value)}`).join('; ')}">
    {#each yTicks as t}
      <line x1={margin.left} x2={width - margin.right} y1={y(t)} y2={y(t)} stroke={GRID} />
      <text x="0" y={y(t)} dominant-baseline="central" font-size="11" fill={MUTED}>{shortBrl(t)}</text>
    {/each}
    <text x="0" y={y(0)} dominant-baseline="central" font-size="11" fill={MUTED}>0</text>
    {#each columns as c, i}
      <g>
        <title>{c.title ?? `${c.label}: ${formatBrl(c.value)}`}</title>
        <path class="mark-grow-y" style:animation-delay="{i * 25}ms"
          d={barPath(x(c.label) ?? 0, y(c.value), x.bandwidth(), Math.max(0, y(0) - y(c.value)), Math.min(6, x.bandwidth() / 4), 'top')}
          fill={c.partial ? BRAND_PALE : c.picked ? BRAND : BRAND_LIGHT}
          stroke={c.partial ? BRAND : 'none'} stroke-dasharray={c.partial ? '4 3' : undefined} />
        {#if showValues || c.picked}
          <text x={(x(c.label) ?? 0) + x.bandwidth() / 2} y={y(c.value) - 5} text-anchor="middle" font-size="10.5"
            fill={c.picked ? BRAND : INK_2} font-weight={c.picked ? 600 : 400}>{shortBrl(c.value)}</text>
        {/if}
        {#if i % every === 0 || c.picked}
          <text x={(x(c.label) ?? 0) + x.bandwidth() / 2} y={height - margin.bottom + 15} text-anchor="middle"
            font-size="11" fill={c.picked ? BRAND : MUTED} font-weight={c.picked ? 600 : 400}>{c.label}</text>
        {/if}
      </g>
    {/each}
    <line x1={margin.left} x2={width - margin.right} y1={y(0)} y2={y(0)} stroke={AXIS} />
    {#each references as r}
      <line x1={margin.left} x2={width - margin.right} y1={y(r.value)} y2={y(r.value)} stroke={r.color ?? MUTED}
        stroke-width="1.5" stroke-dasharray={r.dash ?? '5 4'} />
    {/each}
    {#each refLabels as r}
      <text x={width - margin.right + 5} y={r.y} dominant-baseline="central" font-size="11" fill={r.color ?? MUTED}>{r.name}</text>
    {/each}
  </svg>
</div>

<style>
  .wrap { width: 100%; min-width: 0; }
  svg { display: block; overflow: visible; }
</style>
