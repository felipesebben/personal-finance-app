<!-- A message box: info (green), warn/error (orange), ok (blue). Never red/green for bad/good. -->
<script lang="ts">
  import type { Snippet } from 'svelte'
  let { tone = 'info', children }: { tone?: 'info' | 'warn' | 'error' | 'ok'; children: Snippet } = $props()
</script>

<div class="msg {tone}" role={tone === 'error' ? 'alert' : 'status'}>{@render children()}</div>

<style>
  .msg { border-radius: var(--radius); padding: 0.7rem 0.9rem; font-size: 0.93rem; }
  .info { background: var(--brand-soft); }
  .warn, .error { background: var(--more-soft); color: #7a2f08; }
  .ok { background: var(--less-soft); color: #173f6e; }
</style>
