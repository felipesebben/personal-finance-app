<!-- In-app notices: [text, tone] lines, orange for "more" (e.g. past a target). Nothing drawn without lines. -->
<script lang="ts">
  let { lines = [] }: { lines?: [string, string | null][] } = $props()
</script>

{#if lines.length}
  <div class="notices" role="status">
    {#each lines as [text, tone]}<div class="notice {tone ?? ''}">{text}</div>{/each}
  </div>
{/if}

<style>
  .notices { background: var(--more-soft); border-radius: 14px; padding: 0.7rem 1rem; display: flex;
    flex-direction: column; gap: 0.2rem; }
  .notice { font-size: var(--t-callout); line-height: 1.45; color: var(--ink); }
  .notice.more { color: var(--more-ink); font-weight: 500; }
</style>
