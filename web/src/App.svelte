<!--
  The app shell: a top bar with the pages on a wide screen, a bottom tab bar
  on a phone, the toast, and the page for the current route. Without a
  session (or arriving from a reset link) every route shows Home's login.
-->
<script lang="ts">
  import { PAGES, href, route } from './lib/router.svelte'
  import { endSession, session } from './lib/session.svelte'
  import Icon from './lib/ui/Icon.svelte'
  import Toast from './lib/ui/Toast.svelte'
  import Home from './pages/Home.svelte'
  import AddExpense from './pages/AddExpense.svelte'
  import OurExpenses from './pages/OurExpenses.svelte'
  import MyExpenses from './pages/MyExpenses.svelte'
  import Entries from './pages/Entries.svelte'
  import Settings from './pages/Settings.svelte'

  const resetting = typeof location !== 'undefined' && new URLSearchParams(location.search).has('reset_token')
  const loggedIn = $derived(!!session.token && !resetting)
</script>

{#if loggedIn}
  <header class="topbar">
    <a class="brand" href={href('home')}><img src="/logo.svg" alt="" width="28" height="28" /><span>Home Finances</span></a>
    <nav class="top-nav" aria-label="Pages">
      {#each PAGES.slice(1) as p}
        <a href={href(p.id)} class:active={route.page === p.id} aria-current={route.page === p.id ? 'page' : undefined}>{p.label}</a>
      {/each}
    </nav>
    <button type="button" class="logout" title="Log out ({session.email})" onclick={() => endSession(null)}>
      <Icon name="logout" size={20} /><span>Log out</span>
    </button>
  </header>
{/if}

<main class:with-nav={loggedIn}>
  {#if !loggedIn || route.page === 'home'}
    <Home />
  {:else if route.page === 'add'}
    <AddExpense />
  {:else if route.page === 'ours'}
    <OurExpenses />
  {:else if route.page === 'mine'}
    <MyExpenses />
  {:else if route.page === 'entries'}
    <Entries />
  {:else if route.page === 'settings'}
    <Settings />
  {/if}
</main>

{#if loggedIn}
  <nav class="bottom-nav" aria-label="Pages">
    {#each PAGES as p}
      <a href={href(p.id)} class:active={route.page === p.id} aria-current={route.page === p.id ? 'page' : undefined}>
        <Icon name={p.icon} /><span>{p.short}</span>
      </a>
    {/each}
  </nav>
{/if}

<Toast />

<style>
  .topbar { position: sticky; top: 0; z-index: 20; display: flex; align-items: center; gap: 1.5rem;
    background: rgba(245, 246, 243, 0.92); backdrop-filter: blur(8px); border-bottom: 1px solid var(--line);
    padding: 0 max(var(--gutter), calc((100vw - 1200px) / 2)); height: 56px; }
  .brand { display: flex; align-items: center; gap: 0.5rem; font-weight: 700; color: var(--ink); text-decoration: none; flex: none; }
  .top-nav { display: flex; gap: 0.25rem; flex: 1; overflow-x: auto; }
  .top-nav a { color: var(--ink-2); text-decoration: none; padding: 0.45rem 0.75rem; border-radius: 999px;
    font-weight: 500; white-space: nowrap; }
  .top-nav a:hover { color: var(--ink); background: var(--surface-2); }
  .top-nav a.active { color: var(--brand); background: var(--brand-soft); }
  .logout { display: flex; align-items: center; gap: 0.35rem; border: none; background: none; color: var(--ink-2);
    cursor: pointer; padding: 0.4rem 0.5rem; border-radius: var(--radius); flex: none; }
  .logout:hover { color: var(--ink); background: var(--surface-2); }

  main { max-width: 1200px; margin: 0 auto; padding: 0.75rem var(--gutter) 3rem; }

  .bottom-nav { display: none; }

  @media (max-width: 760px) {
    .top-nav { display: none; }
    .topbar { justify-content: space-between; height: 52px; }
    .logout span { display: none; }
    main.with-nav { padding-bottom: calc(var(--nav-height) + 2rem + env(safe-area-inset-bottom)); }
    .bottom-nav { display: grid; grid-template-columns: repeat(6, 1fr); position: fixed; left: 0; right: 0; bottom: 0;
      z-index: 30; background: var(--surface); border-top: 1px solid var(--line);
      padding-bottom: env(safe-area-inset-bottom); height: calc(var(--nav-height) + env(safe-area-inset-bottom)); }
    .bottom-nav a { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px;
      color: var(--muted); text-decoration: none; font-size: 0.68rem; font-weight: 500; }
    .bottom-nav a.active { color: var(--brand); }
  }
</style>
