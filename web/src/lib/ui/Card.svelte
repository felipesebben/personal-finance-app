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

<section class="card" class:compact style:min-height={minHeight ? `${minHeight}px` : undefined}>
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
  .card {
    background: var(--surface);
    border-radius: var(--radius-card);
    box-shadow: var(--shadow-card);
    padding: 1.25rem 1.4rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    min-width: 0;
  }
  .card.compact { padding: 1rem 1.1rem; gap: 0.5rem; }
  header { display: flex; justify-content: space-between; align-items: flex-start; gap: 0.75rem; flex-wrap: wrap; }
  header p { margin-top: 0.2rem; }
  .actions { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }
  @media (max-width: 560px) {
    .card { padding: 1rem; }
  }
</style>
