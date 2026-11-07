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
  .notices { background: var(--warn-bg); border-left: 4px solid var(--more); border-radius: var(--radius);
    padding: 0.55rem 0.9rem; }
  .notice { font-size: 0.92rem; line-height: 1.45; }
  .notice.more { color: var(--more); font-weight: 600; }
</style>
