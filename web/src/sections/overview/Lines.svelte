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
  h4 { font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--ink-2);
    margin: 0.35rem 0 0.1rem; }
  p { font-size: 0.95rem; }
  p.more { color: var(--more); font-weight: 600; }
  p.less { color: var(--less); font-weight: 600; }
  p.empty { color: var(--muted); font-size: 0.88rem; }
</style>
