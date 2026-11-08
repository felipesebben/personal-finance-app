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
  /* A HUD-style capsule on a translucent material. */
  .toast { position: fixed; left: 50%; transform: translateX(-50%);
    bottom: calc(var(--nav-height) + 1rem + env(safe-area-inset-bottom));
    background: var(--material); -webkit-backdrop-filter: saturate(180%) blur(20px); backdrop-filter: saturate(180%) blur(20px);
    color: var(--ink); padding: 0.7rem 1.2rem; border-radius: 999px; z-index: 50; font-weight: 500;
    display: flex; gap: 0.6rem; align-items: center; box-shadow: var(--shadow-float); max-width: calc(100vw - 32px);
    animation: toast-in 0.3s cubic-bezier(0.2, 0.8, 0.2, 1); }
  span { font-weight: 700; color: var(--brand); }
  .toast.error span { color: var(--more); }
  @keyframes toast-in { from { opacity: 0; transform: translate(-50%, 12px) scale(0.96); } }
  @media (min-width: 761px) { .toast { bottom: 1.5rem; } }
</style>
