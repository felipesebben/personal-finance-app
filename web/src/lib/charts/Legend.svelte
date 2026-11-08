<!--
  A chart's legend (Apple's chart anatomy: it describes what isn't position, like colour or shape).
  Only for marks that aren't labelled where they are: a grey tick for last month, a dark tick for the
  target, a dashed reference, a faded month in progress, the calendar's shading. Lines and reference
  lines named at their end don't need one. Leading-aligned under the plot, in caption text.
-->
<script lang="ts" module>
  export type LegendMark = 'bar' | 'bar-light' | 'tick' | 'target' | 'dash' | 'partial' | 'scale'
  export interface LegendItem { mark: LegendMark; label: string }
</script>

<script lang="ts">
  import { BRAND, BRAND_LIGHT, BRAND_PALE, GREY, INK, MUTED } from './palette'
  let { items }: { items: LegendItem[] } = $props()
</script>

{#if items.length}
  <ul class="legend" aria-hidden="true">
    {#each items as item}
      <li>
        <svg width={item.mark === 'scale' ? 46 : 18} height="12" aria-hidden="true">
          {#if item.mark === 'bar'}<path d="M1,2H13A4,4 0 0 1 17,6A4,4 0 0 1 13,10H1Z" fill={BRAND} />
          {:else if item.mark === 'bar-light'}<path d="M1,2H13A4,4 0 0 1 17,6A4,4 0 0 1 13,10H1Z" fill={BRAND_LIGHT} />
          {:else if item.mark === 'tick'}<line x1="9" x2="9" y1="0" y2="12" stroke={GREY} stroke-width="3" />
          {:else if item.mark === 'target'}<line x1="9" x2="9" y1="0" y2="12" stroke={INK} stroke-width="2.5" />
          {:else if item.mark === 'dash'}<line x1="1" x2="17" y1="6" y2="6" stroke={MUTED} stroke-width="1.5" stroke-dasharray="4 3" />
          {:else if item.mark === 'partial'}<rect x="2" y="1" width="14" height="10" rx="2" fill={BRAND_PALE} stroke={BRAND} stroke-dasharray="3 2" />
          {:else if item.mark === 'scale'}
            {#each [0.15, 0.4, 0.7, 1] as t, i}
              <rect x={i * 12} y="1" width="10" height="10" rx="2.5"
                style:fill="color-mix(in oklab, var(--brand) {t * 100}%, var(--heat-low))" />
            {/each}
          {/if}
        </svg>
        <span>{item.label}</span>
      </li>
    {/each}
  </ul>
{/if}

<style>
  .legend { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 0.35rem 1rem;
    font-size: var(--t-caption); color: var(--muted); }
  li { display: inline-flex; align-items: center; gap: 0.35rem; }
  svg { display: block; flex: none; }
</style>
