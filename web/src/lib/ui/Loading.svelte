<script lang="ts">
  let { text = 'Loading…', height = 160 }: { text?: string; height?: number } = $props()
</script>

<div class="loading" style:min-height="{height}px" aria-busy="true"><span class="dot"></span>{text}</div>

<style>
  .loading { display: flex; align-items: center; justify-content: center; gap: 0.6rem; color: var(--muted); font-size: var(--t-callout); }
  /* An activity indicator. */
  .dot { width: 1.1rem; height: 1.1rem; border-radius: 50%; border: 2px solid var(--fill); border-top-color: var(--muted);
    animation: spin 0.8s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
