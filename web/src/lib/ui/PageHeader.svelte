<script lang="ts">
  let { title, purpose = '' }: { title: string; purpose?: string } = $props()
  $effect(() => {
    document.title = title === 'Home Finances' ? title : `${title} · Home Finances`
  })
</script>

<header>
  <h1>{title}</h1>
  {#if purpose}<p>{purpose}</p>{/if}
</header>

<style>
  /* A large title, then what the page is for in secondary text. */
  header { margin: 0.75rem 0 1.25rem; }
  p { color: var(--muted); margin-top: 0.3rem; max-width: 68ch; font-size: var(--t-headline); }
  @media (max-width: 560px) { header { margin: 0.25rem 0 1rem; } p { font-size: var(--t-callout); } }
</style>
