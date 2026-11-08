<!--
  My expenses: how my own spending is doing. This month day by day and the
  same over time, each with a Show switch (everything I spent = my share of
  shared + my personal expenses, personal only, or my share of shared).
  Nothing here shows a partner's personal spending.
-->
<script lang="ts">
  import { href, route } from '../lib/router.svelte'
  import PageHeader from '../lib/ui/PageHeader.svelte'
  import Tabs from '../lib/ui/Tabs.svelte'
  import Daily from '../sections/Daily.svelte'
  import Overview from '../sections/Overview.svelte'

  const tabs = [
    { id: 'month', label: 'This month' },
    { id: 'trend', label: 'Over time' },
  ]
  const active = $derived(tabs.some((t) => t.id === route.tab) ? route.tab : 'month')
</script>

<PageHeader title="My expenses"
  purpose="How your own spending is doing: your part of what you share, plus what's only yours." />
<Tabs {tabs} />

{#if active === 'month'}
  <Daily lens="My share" key="mine" showView />
{:else}
  <Overview lens="My share" key="mine" showView />
{/if}

<p class="foot"><a href={href('entries')}>Check or fix what was logged →</a></p>

<style>
  .foot { margin-top: 1.5rem; }
</style>
