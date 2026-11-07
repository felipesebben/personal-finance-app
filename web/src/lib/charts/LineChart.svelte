<!--
  Lines over a shared x (days of a month, or months as 1..n), for running
  totals and paces: each series styled by its role (colour, width, dash),
  named at its end rather than in a legend, with a quiet y axis in short
  reais. Hovering (or tapping) shows every series' value at that x.
  Points are { x, y } with y in cents; `xLabel(x)` names an x for the
  readout and the axis ticks.
-->
<script lang="ts">
  import { scaleLinear } from 'd3-scale'
  import { line } from 'd3-shape'
  import { AXIS, GRID, INK, INK_2, MUTED, textWidth } from './palette'
  import { formatBrl, shortBrl } from '../money'

  export interface Series {
    name: string
    points: { x: number; y: number }[]
    color: string
    width?: number
    dash?: string
    /** Draw a dot at the last point (e.g. today). */
    dot?: boolean
    /** Leave its name off the end (shown in the readout only). */
    quiet?: boolean
  }

  let { series, xMin = 1, xMax, height = 240, xLabel = (x: number) => String(x), xTicks = [], yTitle = '', xTitle = '', readoutLabel }: {
    series: Series[]
    xMin?: number
    xMax: number
    height?: number
    xLabel?: (x: number) => string
    xTicks?: number[]
    yTitle?: string
    xTitle?: string
    /** Heads the hover readout (default: xLabel), e.g. "Day 7". */
    readoutLabel?: (x: number) => string
  } = $props()

  let width = $state(480)
  let hover = $state<number | null>(null)

  const named = $derived(series.filter((s) => !s.quiet && s.points.length))
  const endRoom = $derived(Math.min(Math.max(...named.map((s) => textWidth(s.name, 11)), 0) + 12, width * 0.35))
  const margin = $derived({ top: yTitle ? 22 : 10, right: endRoom, bottom: xTitle ? 38 : 24, left: 52 })
  const yMax = $derived(Math.max(...series.flatMap((s) => s.points.map((p) => p.y)), 1))
  const x = $derived(scaleLinear().domain([xMin, Math.max(xMax, xMin + 1)]).range([margin.left, width - margin.right]))
  const y = $derived(scaleLinear().domain([0, yMax]).nice(4).range([height - margin.bottom, margin.top]))
  const yTicks = $derived(y.ticks(4))
  const ticksX = $derived(xTicks.length ? xTicks : x.ticks(Math.min(6, xMax - xMin)).filter(Number.isInteger))
  const path = $derived((pts: { x: number; y: number }[]) =>
    line<{ x: number; y: number }>().x((p) => x(p.x)).y((p) => y(p.y))(pts) ?? '')

  // End labels, nudged apart so they don't overlap.
  const labels = $derived.by(() => {
    const items = named.map((s) => {
      const last = s.points[s.points.length - 1]
      return { name: s.name, color: s.color, x: x(last.x), y: y(last.y) }
    }).sort((a, b) => a.y - b.y)
    for (let i = 1; i < items.length; i++) if (items[i].y - items[i - 1].y < 13) items[i].y = items[i - 1].y + 13
    return items
  })

  function move(e: PointerEvent) {
    const rect = (e.currentTarget as SVGElement).getBoundingClientRect()
    const v = Math.round(x.invert(e.clientX - rect.left))
    hover = Math.min(Math.max(v, xMin), xMax)
  }
  const readout = $derived(hover === null ? [] : series.map((s) => ({
    name: s.name, color: s.color, point: s.points.find((p) => p.x === hover),
  })).filter((r) => r.point))
</script>

<div class="wrap" bind:clientWidth={width}>
  <svg {width} {height} role="img" aria-label={named.map((s) => `${s.name}: ${shortBrl(s.points.at(-1)?.y ?? 0)}`).join('; ')}
    onpointermove={move} onpointerleave={() => (hover = null)}>
    {#each yTicks as t}
      <line x1={margin.left} x2={width - margin.right} y1={y(t)} y2={y(t)} stroke={GRID} />
      <text x={margin.left - 6} y={y(t)} text-anchor="end" dominant-baseline="central" font-size="11" fill={MUTED}>{shortBrl(t)}</text>
    {/each}
    <line x1={margin.left} x2={width - margin.right} y1={height - margin.bottom} y2={height - margin.bottom} stroke={AXIS} />
    {#each ticksX as t}
      <text x={x(t)} y={height - margin.bottom + 15} text-anchor="middle" font-size="11" fill={MUTED}>{xLabel(t)}</text>
    {/each}
    {#if yTitle}<text x={margin.left - 46} y="11" font-size="11" fill={MUTED}>{yTitle}</text>{/if}
    {#if xTitle}<text x={width - margin.right} y={height - 2} text-anchor="end" font-size="11" fill={MUTED}>{xTitle}</text>{/if}
    {#each series as s}
      {#if s.points.length > 1}
        <path d={path(s.points)} fill="none" stroke={s.color} stroke-width={s.width ?? 2} stroke-dasharray={s.dash}
          stroke-linejoin="round" stroke-linecap="round" />
      {/if}
      {#if s.dot || s.points.length === 1}
        {@const last = s.points[s.points.length - 1]}
        {#if last}<circle cx={x(last.x)} cy={y(last.y)} r="4" fill={s.color} />{/if}
      {/if}
    {/each}
    {#each labels as l}
      <text x={l.x + 6} y={l.y} dominant-baseline="central" font-size="11" fill={l.color} font-weight="600">{l.name}</text>
    {/each}
    {#if hover !== null}
      <line x1={x(hover)} x2={x(hover)} y1={margin.top} y2={height - margin.bottom} stroke={INK_2} stroke-opacity="0.35" />
    {/if}
  </svg>
  {#if hover !== null && readout.length}
    <div class="readout" style:left="{Math.min(x(hover) + 10, width - 190)}px">
      <b>{(readoutLabel ?? xLabel)(hover)}</b>
      {#each readout as r}
        <div><span class="sw" style:background={r.color}></span>{r.name}: {formatBrl(r.point!.y)}</div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .wrap { position: relative; width: 100%; min-width: 0; touch-action: pan-y; }
  svg { display: block; overflow: visible; }
  .readout { position: absolute; top: 4px; background: rgba(255, 255, 255, 0.96); border: 1px solid var(--line);
    border-radius: 0.5rem; padding: 0.4rem 0.6rem; font-size: 0.78rem; pointer-events: none; min-width: 170px;
    box-shadow: var(--shadow-card); color: var(--ink); }
  .sw { display: inline-block; width: 0.6rem; height: 0.6rem; border-radius: 2px; margin-right: 0.35rem; }
</style>
