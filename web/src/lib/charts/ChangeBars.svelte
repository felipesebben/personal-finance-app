<!--
  The change beside each ranked bar: a diverging bar from zero, orange to the
  right for spending more, blue to the left for less, the signed value with
  its arrow written at the tip, so colour is never alone. `rows` line up
  one-for-one with a RankedBars beside it (same BAR_ROW). A row with value
  null has no comparison and says so in its text.
-->
<script lang="ts">
  import { scaleLinear } from 'd3-scale'
  import { AXIS, BAR_ROW, GRID, INK_2, LESS, MORE, MUTED, X_AXIS, barPath, fittedTicks, textWidth } from './palette'

  let { rows, top = 4, format = (v: number) => String(v), axis = true }: {
    rows: { label: string; value: number | null; text: string }[]
    top?: number
    /** Tick labels along the bottom (signed: "+R$ 500", "-20%"). */
    format?: (v: number) => string
    axis?: boolean
  } = $props()

  let width = $state(200)
  const room = $derived(Math.max(...rows.map((r) => textWidth(r.text, 11.5)), 30) + 8)
  const max = $derived(Math.max(...rows.map((r) => Math.abs(r.value ?? 0)), 1))
  const x = $derived(scaleLinear().domain([-max, max]).range([room, Math.max(room + 20, width - room)]))
  const plotBottom = $derived(top + rows.length * BAR_ROW)
  const height = $derived(plotBottom + (axis ? X_AXIS : 4))
  // Few ticks, symmetric round steps around zero; the zero line is the axis.
  const ticks = $derived(fittedTicks(x, -max, max, format))
</script>

<div class="wrap" bind:clientWidth={width}>
  <svg {width} {height} role="img"
    aria-label="Change chart: more to the right, less to the left of zero. {rows.map((r) => `${r.label}: ${r.text}`).join('; ')}">
    {#each ticks as t}
      <line x1={x(t)} x2={x(t)} y1={top} y2={plotBottom + (axis ? 3 : 0)} stroke={GRID} />
    {/each}
    <line x1={x(0)} x2={x(0)} y1={top} y2={plotBottom + (axis ? 3 : 0)} stroke={AXIS} />
    {#if axis}
      <text x={x(0)} y={plotBottom + 15} font-size="11" fill={MUTED} text-anchor="middle">0</text>
      {#each ticks as t}
        <text x={x(t)} y={plotBottom + 15} font-size="11" fill={MUTED} text-anchor="middle">{format(t)}</text>
      {/each}
    {/if}
    {#each rows as row, i}
      {@const y = top + i * BAR_ROW}
      {@const v = row.value ?? 0}
      <g>
        <title>{row.label}: {row.text}</title>
        {#if row.value !== null}
          <path class="mark-grow-x" style:transform-origin={v < 0 ? 'right center' : 'left center'}
            d={barPath(Math.min(x(0), x(v)), y + (BAR_ROW - 18) / 2, Math.abs(x(v) - x(0)), 18, 5, v < 0 ? 'left' : 'right')}
            fill={v > 0 ? MORE : LESS} />
        {/if}
        <text x={row.value === null ? x(0) + 6 : v >= 0 ? x(v) + 5 : x(v) - 5} y={y + BAR_ROW / 2}
          dominant-baseline="central" font-size="11.5" text-anchor={row.value !== null && v < 0 ? 'end' : 'start'}
          fill={row.value === null ? INK_2 : v > 0 ? MORE : v < 0 ? LESS : INK_2}
          font-weight={row.value ? 500 : 400}>{row.text}</text>
      </g>
    {/each}
  </svg>
</div>

<style>
  .wrap { width: 100%; min-width: 0; }
  svg { display: block; overflow: visible; }
</style>
