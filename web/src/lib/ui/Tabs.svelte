<!--
  Page tabs, kept in the URL (#/ours/month) so a reload or the back button
  lands on the same tab. Scrolls sideways on a phone rather than wrapping.
  Bind `active` to read which tab is showing.
-->
<script lang="ts">
  import { route, setTab } from '../router.svelte'
  let { tabs }: { tabs: { id: string; label: string }[] } = $props()
  const active = $derived(tabs.some((t) => t.id === route.tab) ? route.tab : tabs[0]?.id)
</script>

<div class="tabs" role="tablist">
  {#each tabs as tab}
    <button type="button" role="tab" aria-selected={active === tab.id} class:active={active === tab.id}
      onclick={() => setTab(tab.id)}>{tab.label}</button>
  {/each}
</div>

<style>
  .tabs { display: flex; gap: 0.25rem; overflow-x: auto; border-bottom: 1px solid var(--line); margin-bottom: 1.25rem;
    scrollbar-width: none; }
  button { flex: none; border: none; background: none; padding: 0.65rem 0.9rem; cursor: pointer; color: var(--ink-2);
    font-weight: 500; border-bottom: 3px solid transparent; margin-bottom: -1px; white-space: nowrap; }
  button:hover { color: var(--ink); }
  button.active { color: var(--brand); border-bottom-color: var(--brand); }
</style>
