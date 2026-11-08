<!--
  The change beside each ranked bar: a diverging bar from zero, orange to the
  right for spending more, blue to the left for less, the signed value with
  its arrow written at the tip, so colour is never alone. `rows` line up
  one-for-one with a RankedBars beside it (same BAR_ROW). A row with value
  null has no comparison and says so in its text.
-->
<script lang="ts">
  import { scaleLinear } from 'd3-scale'
  import { AXIS, BAR_ROW, INK_2, LESS, MORE, barPath, textWidth } from './palette'

  let { rows, top = 4 }: {
    rows: { label: string; value: number | null; text: string }[]
    top?: number
  } = $props()

  let width = $state(200)
  const room = $derived(Math.max(...rows.map((r) => textWidth(r.text, 11.5)), 30) + 8)
  const max = $derived(Math.max(...rows.map((r) => Math.abs(r.value ?? 0)), 1))
  const x = $derived(scaleLinear().domain([-max, max]).range([room, Math.max(room + 20, width - room)]))
  const height = $derived(rows.length * BAR_ROW + top + 4)
</script>

<div class="wrap" bind:clientWidth={width}>
  <svg {width} {height} role="img" aria-label={rows.map((r) => `${r.label}: ${r.text}`).join('; ')}>
    <line x1={x(0)} x2={x(0)} y1={top} y2={height - 2} stroke={AXIS} />
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
          font-weight={row.value ? 600 : 400}>{row.text}</text>
      </g>
    {/each}
  </svg>
</div>

<style>
  .wrap { width: 100%; min-width: 0; }
  svg { display: block; overflow: visible; }
</style>
