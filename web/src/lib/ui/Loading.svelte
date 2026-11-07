<script lang="ts">
  let { text = 'Loading…', height = 160 }: { text?: string; height?: number } = $props()
</script>

<div class="loading" style:min-height="{height}px" aria-busy="true"><span class="dot"></span>{text}</div>

<style>
  .loading { display: flex; align-items: center; justify-content: center; gap: 0.6rem; color: var(--muted); font-size: 0.9rem; }
  .dot { width: 0.6rem; height: 0.6rem; border-radius: 50%; background: var(--brand-light); animation: pulse 1s infinite alternate; }
  @keyframes pulse { from { opacity: 0.3 } to { opacity: 1 } }
</style>
