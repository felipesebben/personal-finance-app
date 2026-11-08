<!-- Sentences with a tone, as a KPI's lines: ▲ orange for more, ▼ blue for less, ink otherwise. -->
<script lang="ts">
  import type { Line } from '../../lib/overview/shaping'
  let { lines, title = '', empty = '' }: { lines: Line[]; title?: string; empty?: string } = $props()
</script>

<div class="lines">
  {#if title}<h4>{title}</h4>{/if}
  {#if lines.length}
    {#each lines as [text, tone]}<p class={tone ?? ''}>{text}</p>{/each}
  {:else if empty}
    <p class="empty">{empty}</p>
  {/if}
</div>

<style>
  .lines { display: flex; flex-direction: column; gap: 0.25rem; }
  h4 { font-size: var(--t-footnote); font-weight: 400; letter-spacing: 0; color: var(--ink-2);
    margin: 0.35rem 0 0.1rem; }
  p { font-size: var(--t-callout); }
  p.more { color: var(--more); }
  p.less { color: var(--less); }
  p.empty { color: var(--muted); font-size: var(--t-subhead); }
</style>
