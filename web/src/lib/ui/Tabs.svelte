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
  /* A segmented control (iOS): a grey track and a raised thumb on the picked tab. Scrolls sideways on a phone. */
  .tabs { display: flex; gap: 2px; overflow-x: auto; margin-bottom: 1.25rem; padding: 2px; width: fit-content;
    max-width: 100%; background: var(--fill); border-radius: 9px; scrollbar-width: none; }
  .tabs::-webkit-scrollbar { display: none; }
  button { flex: none; border: none; background: none; padding: 0.4rem 1rem; cursor: pointer; color: var(--ink);
    font-size: 0.875rem; font-weight: 500; border-radius: 7px; white-space: nowrap;
    transition: background 0.2s ease, box-shadow 0.2s ease; }
  button:hover:not(.active) { background: var(--fill-2); }
  button.active { background: var(--thumb); font-weight: 600;
    box-shadow: 0 3px 8px rgba(0, 0, 0, 0.12), 0 3px 1px rgba(0, 0, 0, 0.04); }
</style>
