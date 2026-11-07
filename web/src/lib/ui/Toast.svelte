<!-- The confirmation after a save (session showToast), bottom centre, gone after a few seconds. -->
<script lang="ts">
  import { toast } from '../session.svelte'
  let visible = $state(false)
  let timer: ReturnType<typeof setTimeout> | undefined
  $effect(() => {
    if (toast.id === 0) return
    visible = true
    clearTimeout(timer)
    timer = setTimeout(() => (visible = false), 3500)
  })
</script>

{#if visible && toast.message}
  <div class="toast {toast.tone}" role="status" aria-live="polite">
    <span aria-hidden="true">{toast.tone === 'ok' ? '✓' : '!'}</span>{toast.message}
  </div>
{/if}

<style>
  .toast { position: fixed; left: 50%; transform: translateX(-50%); bottom: calc(var(--nav-height) + 1rem);
    background: var(--ink); color: #fff; padding: 0.7rem 1.1rem; border-radius: var(--radius); z-index: 50;
    display: flex; gap: 0.6rem; align-items: center; box-shadow: var(--shadow-card); max-width: calc(100vw - 32px); }
  .toast.error { background: var(--more); }
  span { font-weight: 700; }
  @media (min-width: 761px) { .toast { bottom: 1.5rem; } }
</style>
