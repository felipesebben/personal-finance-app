<!--
  Sparkbars over months for a KPI card: one bar per month, named underneath
  ("Jun", "Jul"…), the picked month brand green and the rest a lighter
  green, a month in progress faded with a dashed outline, and an optional
  dashed ink line at a reference (the usual month), so "above or below
  usual" reads at a glance. Each bar's tooltip gives its amount.
-->
<script lang="ts">
  import { BRAND, BRAND_LIGHT, BRAND_PALE, INK, MUTED, SPARK_HEIGHT } from './palette'

  let { bars, reference = null, referenceName = 'usual', height = SPARK_HEIGHT }: {
    bars: { label: string; value: number; title: string; picked?: boolean; partial?: boolean }[]
    reference?: number | null
    referenceName?: string
    height?: number
  } = $props()

  let width = $state(200)
  const LABEL = 14
  const plot = $derived(height - LABEL)
  const max = $derived(Math.max(...bars.map((b) => b.value), reference ?? 0, 1))
  const gap = 5
  const bw = $derived(bars.length ? Math.max(3, (width - gap * (bars.length - 1)) / bars.length) : 0)
  const y = (v: number) => plot - (Math.max(0, v) / max) * (plot - 3)
</script>

<div class="wrap" bind:clientWidth={width}>
  <svg {width} {height} role="img"
    aria-label={bars.map((b) => b.title).join('; ') + (reference !== null ? `; dashed line: ${referenceName}` : '')}>
    {#each bars as b, i}
      <g>
        <title>{b.title}</title>
        <rect x={i * (bw + gap)} y={y(b.value)} width={bw} height={Math.max(1.5, plot - y(b.value))} rx="2"
          fill={b.partial ? BRAND_PALE : b.picked ? BRAND : BRAND_LIGHT}
          stroke={b.partial ? BRAND : 'none'} stroke-dasharray={b.partial ? '3 2' : undefined} />
        <text x={i * (bw + gap) + bw / 2} y={height - 2} text-anchor="middle" font-size="9.5"
          fill={b.picked ? BRAND : MUTED} font-weight={b.picked ? 600 : 400}>{b.label}</text>
      </g>
    {/each}
    <line x1="0" x2={width} y1={plot} y2={plot} stroke="#aab2ac" />
    {#if reference !== null}
      <line x1="0" x2={width} y1={y(reference)} y2={y(reference)} stroke={INK} stroke-width="1.2" stroke-dasharray="3 2">
        <title>{referenceName}</title>
      </line>
    {/if}
  </svg>
</div>

<style>
  .wrap { width: 100%; margin-top: auto; padding-top: 0.5rem; }
  svg { display: block; overflow: visible; }
</style>
