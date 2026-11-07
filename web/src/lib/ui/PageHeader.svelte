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
  header { margin: 0.5rem 0 1.25rem; }
  p { color: var(--ink-2); margin-top: 0.35rem; max-width: 68ch; }
</style>
