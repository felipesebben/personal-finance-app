<!-- The green "what this is for" box that opens a section: two lines at most. -->
<script lang="ts">
  let { headline, body = '' }: { headline: string; body?: string } = $props()
</script>

<div class="lede">
  <span class="i" aria-hidden="true">i</span>
  <div><b>{headline}</b>{#if body}<span>{body}</span>{/if}</div>
</div>

<style>
  /* Plain secondary text with an info glyph, as Apple's explanatory headers; no box competing with the cards. */
  .lede { display: flex; gap: 0.6rem; align-items: flex-start; color: var(--muted); padding: 0 0.15rem;
    font-size: 0.9375rem; }
  .i { flex: none; width: 1.25rem; height: 1.25rem; border-radius: 50%; background: var(--brand-soft); color: var(--brand);
    font-weight: 700; font-size: 0.75rem; display: grid; place-items: center; margin-top: 0.1rem;
    font-family: Georgia, serif; font-style: italic; }
  b { display: block; color: var(--ink); font-weight: 600; }
</style>
