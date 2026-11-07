<!-- The green "what this is for" box that opens a section: two lines at most. -->
<script lang="ts">
  let { headline, body = '' }: { headline: string; body?: string } = $props()
</script>

<div class="lede">
  <span class="i" aria-hidden="true">i</span>
  <div><b>{headline}</b>{#if body}<span>{body}</span>{/if}</div>
</div>

<style>
  .lede { display: flex; gap: 0.6rem; align-items: flex-start; background: var(--brand-soft);
    border-radius: var(--radius); padding: 0.65rem 0.8rem; color: var(--ink); }
  .i { flex: none; width: 1.35rem; height: 1.35rem; border-radius: 50%; background: var(--brand); color: #fff;
    font-weight: 700; font-size: 0.8rem; display: grid; place-items: center; margin-top: 0.1rem; }
  b { display: block; }
</style>
