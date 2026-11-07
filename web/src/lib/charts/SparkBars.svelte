<!--
  Sparkbars for a KPI card: one bar per month (or day), the last (or
  `highlight`) brand green and the rest a pale green, a faded bar for a
  month in progress. No axes: a gist of the shape. Each bar has a tooltip.
-->
<script lang="ts">
  import { BRAND, BRAND_LIGHT, BRAND_PALE, SPARK_HEIGHT } from './palette'

  let { values, labels = [], highlight = -1, partial = -1, height = SPARK_HEIGHT }: {
    values: number[]
    labels?: string[]
    highlight?: number | null
    partial?: number
    height?: number
  } = $props()

  let width = $state(200)
  const max = $derived(Math.max(...values.map((v) => Math.abs(v)), 1))
  const gap = 4
  const bw = $derived(values.length ? Math.max(2, (width - gap * (values.length - 1)) / values.length) : 0)
  // -1 (default) = the last bar; null = none.
  const hi = $derived(highlight === null ? -1 : highlight >= 0 ? highlight : values.length - 1)
</script>

<div class="wrap" bind:clientWidth={width}>
  <svg {width} {height} aria-hidden="true">
    {#each values as v, i}
      {@const h = Math.max(1.5, (Math.abs(v) / max) * (height - 4))}
      <rect x={i * (bw + gap)} y={height - h} width={bw} {height} rx="2"
        fill={i === partial ? BRAND_PALE : i === hi ? BRAND : BRAND_LIGHT}
        stroke={i === partial ? BRAND : 'none'} stroke-dasharray={i === partial ? '3 2' : undefined}>
        {#if labels[i]}<title>{labels[i]}</title>{/if}
      </rect>
    {/each}
  </svg>
</div>

<style>
  .wrap { width: 100%; margin-top: 0.5rem; }
  svg { display: block; }
</style>
