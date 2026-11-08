<!-- A message box: info (green), warn/error (orange), ok (blue). Never red/green for bad/good. -->
<script lang="ts">
  import type { Snippet } from 'svelte'
  let { tone = 'info', children }: { tone?: 'info' | 'warn' | 'error' | 'ok'; children: Snippet } = $props()
</script>

<div class="msg {tone}" role={tone === 'error' ? 'alert' : 'status'}>{@render children()}</div>

<style>
  .msg { border-radius: 12px; padding: 0.75rem 0.95rem; font-size: 0.9375rem; }
  .info { background: var(--brand-soft); }
  .warn, .error { background: var(--more-soft); color: var(--more-ink); }
  .ok { background: var(--less-soft); color: var(--less-ink); }
</style>
