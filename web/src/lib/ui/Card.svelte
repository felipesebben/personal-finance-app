<!--
  One card, one question: the question as its heading, then the answer.
  White on the grey page with a soft shadow, so each card reads as one region.
  `minHeight` lines up a row of cards (a grid row also stretches them to the tallest).
-->
<script lang="ts">
  import type { Snippet } from 'svelte'
  let { title = '', subtitle = '', minHeight = 0, compact = false, children, actions }: {
    title?: string
    subtitle?: string
    minHeight?: number
    compact?: boolean
    children?: Snippet
    actions?: Snippet
  } = $props()
</script>

<section class="card" class:compact style:--min-height={minHeight ? `${minHeight}px` : undefined}>
  {#if title || actions}
    <header>
      <div>
        {#if title}<h3>{title}</h3>{/if}
        {#if subtitle}<p class="caption">{subtitle}</p>{/if}
      </div>
      {#if actions}<div class="actions">{@render actions()}</div>{/if}
    </header>
  {/if}
  {@render children?.()}
</section>

<style>
  /* An inset grouped section: flat white on the grey page, no border or shadow. */
  .card {
    background: var(--surface);
    border-radius: var(--radius-card);
    box-shadow: var(--shadow-card);
    padding: 1.35rem 1.5rem 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    min-width: 0;
    min-height: var(--min-height, 0);
  }
  .card.compact { padding: 0.95rem 1.05rem; gap: 0.5rem; }
  /* The question as a headline, the answer under it as the chart's summary; the card's own pickers top right. */
  header { display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem 1rem; flex-wrap: wrap; }
  header > div:first-child { flex: 1 1 16rem; min-width: 0; }
  header p { margin-top: 0.2rem; font-size: var(--t-callout); color: var(--muted); }
  .actions { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; justify-content: flex-end; margin-left: auto; }
  @media (max-width: 560px) {
    /* One card per row on a phone: no row to line up with, so no reserved height. */
    .card { padding: 1rem; border-radius: 14px; min-height: 0; }
  }
</style>
