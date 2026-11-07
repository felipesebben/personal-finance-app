<!--
  Ranked horizontal bars, the one way the app ranks things (categories,
  sub-categories, days): names left-aligned in a column only as wide as the
  longest name, the value written at the bar's tip, the picked bar brand
  green and the rest a lighter green. Optional bullet marks per row: a grey
  tick where last month stood by the same day (`tick`) and a dark tick at the
  target (`target`). An optional dashed `reference` line (e.g. the month's
  average day) with its label. Values are numbers in any unit (cents).
  Clicking a row calls `onpick` (the picker is still a pill row beside it,
  this is a convenience).
-->
<script lang="ts">
  import { scaleLinear } from 'd3-scale'
  import { BAR_ROW, BRAND, BRAND_LIGHT, GREY, GRID, INK, INK_2, MUTED, clip, textWidth } from './palette'

  export interface Bar {
    label: string
    value: number
    text: string
    tick?: number | null
    target?: number | null
    picked?: boolean
    title?: string
  }

  let { rows, reference = null, referenceLabel = '', onpick, maxLabel = 22 }: {
    rows: Bar[]
    reference?: number | null
    referenceLabel?: string
    onpick?: (label: string) => void
    maxLabel?: number
  } = $props()

  let width = $state(320)
  const names = $derived(rows.map((r) => clip(r.label, maxLabel)))
  const nameWidth = $derived(Math.min(Math.max(...names.map((n) => textWidth(n)), 40) + 10, width * 0.42))
  const textRoom = $derived(Math.max(...rows.map((r) => textWidth(r.text, 11.5)), 30) + 10)
  const max = $derived(Math.max(...rows.flatMap((r) => [r.value, r.tick ?? 0, r.target ?? 0]), reference ?? 0, 1))
  const x = $derived(scaleLinear().domain([0, max]).range([nameWidth, Math.max(nameWidth + 40, width - textRoom)]))
  const top = $derived(reference !== null && referenceLabel ? 18 : 4)
  const height = $derived(rows.length * BAR_ROW + top + 4)
  const ticks = $derived(x.ticks(4).filter((t) => t > 0))
  const barH = BAR_ROW - 12

  /** The value sits at the bar's tip; a tick that would cut through it pushes it just past the tick. */
  function textX(row: Bar): number {
    let at = x(row.value) + 6
    const w = textWidth(row.text, 11.5)
    const marks = [row.tick, row.target].filter((m): m is number => m !== null && m !== undefined).map((m) => x(m))
      .sort((a, b) => a - b)
    for (const m of marks) if (m >= at - 4 && m <= at + w + 4) at = m + 6
    return at
  }
</script>

<div class="wrap" bind:clientWidth={width}>
  <svg {width} {height} role="img" aria-label={rows.map((r) => `${r.label}: ${r.text}`).join('; ')}>
    {#each ticks as t}
      <line x1={x(t)} x2={x(t)} y1={top} y2={height - 2} stroke={GRID} />
    {/each}
    <line x1={nameWidth} x2={nameWidth} y1={top} y2={height - 2} stroke="#aab2ac" />
    {#each rows as row, i}
      {@const y = top + i * BAR_ROW}
      <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
      <g class:pickable={!!onpick} onclick={() => onpick?.(row.label)} role={onpick ? 'button' : undefined}
        tabindex={onpick ? 0 : undefined} onkeydown={(e) => e.key === 'Enter' && onpick?.(row.label)}>
        <title>{row.title ?? `${row.label}: ${row.text}`}</title>
        <rect x="0" {y} width={width} height={BAR_ROW} fill="transparent" />
        <text x="0" y={y + BAR_ROW / 2} dominant-baseline="central" font-size="12" fill={INK}
          font-weight={row.picked ? 600 : 400}>{names[i]}</text>
        <rect x={nameWidth} y={y + 6} width={Math.max(0, x(row.value) - nameWidth)} height={barH} rx="3"
          fill={row.picked ? BRAND : BRAND_LIGHT} />
        {#if row.tick !== null && row.tick !== undefined}
          <line x1={x(row.tick)} x2={x(row.tick)} y1={y + 3} y2={y + BAR_ROW - 3} stroke={GREY} stroke-width="3" />
        {/if}
        {#if row.target !== null && row.target !== undefined}
          <line x1={x(row.target)} x2={x(row.target)} y1={y + 2} y2={y + BAR_ROW - 2} stroke={INK} stroke-width="2.5" />
        {/if}
        <text x={textX(row)} y={y + BAR_ROW / 2}
          dominant-baseline="central" font-size="11.5" fill={INK_2}>{row.text}</text>
      </g>
    {/each}
    {#if reference !== null}
      <line x1={x(reference)} x2={x(reference)} y1={top - 2} y2={height - 2} stroke={MUTED} stroke-dasharray="4 3" />
      {#if referenceLabel}
        <text x={x(reference)} y="11" font-size="11" fill={MUTED} text-anchor="middle">{referenceLabel}</text>
      {/if}
    {/if}
  </svg>
</div>

<style>
  .wrap { width: 100%; min-width: 0; }
  svg { display: block; overflow: visible; }
  .pickable { cursor: pointer; }
  .pickable:hover rect:nth-of-type(2) { filter: brightness(0.92); }
  g:focus { outline: none; }
  g:focus-visible text:first-of-type { text-decoration: underline; }
</style>
